#define PONG248_CAPACITY 487079936ULL
#define PONG248_POLICY_ID "c5f530cb117629e2"
/* SPDX-License-Identifier: GPL-2.0-only */
/* Local Pong LAB policy. Physical sectors are always 512-byte units. */
static int pong248_range_allowed(unsigned long long capacity,
        unsigned long long start, unsigned long long sectors, int ordinary_write)
{
    if (capacity != PONG248_CAPACITY || !sectors || start >= capacity ||
        sectors > capacity - start)
        return 0;
    if (start >= 14750272ULL && start < 14783040ULL &&
        sectors <= 14783040ULL - start)
        return 1;
    if (start >= 15307328ULL && start < 487079896ULL &&
        sectors <= 487079896ULL - start)
        return 1;
    if (start >= 65600ULL && start < 65608ULL &&
        sectors <= 65608ULL - start && ordinary_write)
        return 1;
    return 0;
}
