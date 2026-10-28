/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/pong309-ufs.h>
#include <linux/blkdev.h>
#include <scsi/scsi_device.h>
#include <scsi/scsi_host.h>
/* Disk letters are assigned by probe completion order. Bind the immutable
 * range policy to UFS LUN zero and its exact independently captured capacity.
 * USB/SATA lookalikes, other UFS LUNs and unknown devices fail closed. */
bool pong309_is_data_lun(struct gendisk *disk,
                                      unsigned long long expected_capacity)
{
    struct device *parent;
    struct scsi_device *sdev;
    if (!disk || get_capacity(disk) != expected_capacity)
        return false;
    parent = disk_to_dev(disk)->parent;
    if (!parent || !scsi_is_sdev_device(parent))
        return false;
    sdev = to_scsi_device(parent);
    return sdev->lun == 0 && sdev->host && sdev->host->hostt &&
           sdev->host->hostt->proc_name &&
           !strcmp(sdev->host->hostt->proc_name, "ufshcd");
}
