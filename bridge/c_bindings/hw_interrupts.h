/*
 * DBAI Hardware Interrupt Bindings — Header
 */

#ifndef HW_INTERRUPTS_H
#define HW_INTERRUPTS_H

#ifdef __cplusplus
extern "C" {
#endif

/* ======================================================================
 * Datenstrukturen
 * ====================================================================== */

typedef struct {
    unsigned long total_mb;
    unsigned long free_mb;
    unsigned long used_mb;
    unsigned long shared_mb;
    unsigned long buffer_mb;
    unsigned long swap_total;
    unsigned long swap_free;
    long uptime_sec;
    unsigned short procs;
} MemoryInfo;

typedef struct {
    int core_id;
    int online;
    long temperature_mc;     /* Milligrad Celsius */
    unsigned long frequency_khz;
} CpuInfo;

typedef struct {
    char mount_point[256];
    unsigned long long total_bytes;
    unsigned long long free_bytes;
    unsigned long long avail_bytes;
    unsigned long long used_bytes;
    double usage_percent;
} DiskInfo;

/* ======================================================================
 * Funktions-Deklarationen
 * ====================================================================== */

/* Speicher-Informationen */
int get_memory_info(MemoryInfo *info);

/* CPU-Informationen */
int get_cpu_count(void);
int get_cpu_info(int core_id, CpuInfo *info);

/* Disk-Informationen */
int get_disk_info(const char *mount_point, DiskInfo *info);

/* Interrupt-Zählung */
long get_interrupt_count(void);

/* System-Uptime in Sekunden */
double get_uptime_seconds(void);

/* Zeitstempel in Nanosekunden (monoton) */
long long get_timestamp_ns(void);

#ifdef __cplusplus
}
#endif

#endif /* HW_INTERRUPTS_H */
