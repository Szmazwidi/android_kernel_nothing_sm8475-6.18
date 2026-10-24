/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PONG309_UFS_IDENTITY_H
#define PONG309_UFS_IDENTITY_H
#include <linux/types.h>
struct gendisk;
bool pong309_is_data_lun(struct gendisk *disk, unsigned long long expected_capacity);
#endif
