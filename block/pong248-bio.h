/* SPDX-License-Identifier: GPL-2.0-only */
#ifdef CONFIG_PONG_LAB_GUARDS
/* Immutable LAB allowlist: after stacked-device remapping, every physical BIO
 * is checked again. Neither device-node aliases nor a raw-LUN DM mapping can
 * turn a protected sector into an authorized data sector. No runtime switch.
 * This does not mediate SCSI passthrough or arbitrary hostile kernel code;
 * the separate inherited syscall filter and module lock remain required. */
#include "pong248-range.h"
#include <linux/pong309-ufs.h>
static bool pong248_bio_allowed(struct bio *bio)
{
    struct block_device *bdev = bio->bi_bdev;
    const char *name = bdev->bd_disk->disk_name;
    sector_t start = bio->bi_iter.bi_sector, size = bio_sectors(bio);
    enum req_op op = bio_op(bio);

    if (op == REQ_OP_READ || (op == REQ_OP_WRITE && !size) ||
        (op == REQ_OP_FLUSH && !size))
        return true;
    /* These are intermediate or RAM devices. Backing physical BIOs traverse
     * this function again, including DM default-key and loop-backed APEX. */
    if (!strncmp(name, "dm-", 3) || !strncmp(name, "loop", 4) ||
        !strncmp(name, "zram", 4) || !strncmp(name, "ram", 3))
        return true;
    if (!pong309_is_data_lun(bdev->bd_disk, PONG248_CAPACITY))
        goto denied;
    /* __submit_bio runs after blk_partition_remap. The sector is already
     * disk-relative even when bi_bdev still identifies a partition. Never
     * add bd_start_sect twice; reject an inconsistent partition BIO. */
    if (bdev_is_partition(bdev) && !bio_flagged(bio, BIO_REMAPPED))
        goto denied;
    if ((op == REQ_OP_WRITE || op == REQ_OP_DISCARD ||
         op == REQ_OP_SECURE_ERASE || op == REQ_OP_WRITE_ZEROES) &&
        pong248_range_allowed(get_capacity(bdev->bd_disk), start, size,
                              op == REQ_OP_WRITE))
        return true;
denied:
    pr_warn_ratelimited("PONG248_BLOCKED policy=%s disk=%s op=%u sector=%llu count=%llu\n",
                       PONG248_POLICY_ID, name, op,
                       (unsigned long long)start, (unsigned long long)size);
    return false;
}
static int __init pong248_guard_init(void)
{
    pr_info("PONG248_PHYSICAL_WRITE_GUARD policy=%s capacity=%llu always_on=1\n",
            PONG248_POLICY_ID, PONG248_CAPACITY);
    return 0;
}
early_initcall(pong248_guard_init);
#else /* !CONFIG_PONG_LAB_GUARDS */
static inline bool pong248_bio_allowed(struct bio *bio)
{
    return true;
}
#endif /* CONFIG_PONG_LAB_GUARDS */
