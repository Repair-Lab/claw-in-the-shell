/*
 * DBAI Hardware Interrupt Bindings
 * =================================
 * Low-Level C-Code für Hardware-Zugriff.
 * Wird von Python über ctypes aufgerufen.
 *
 * Funktionen:
 * - CPU-Temperatur direkt aus MSR lesen
 * - Hardware-Interrupts zählen
 * - Speicher-Informationen via sysinfo()
 * - Disk-Health via S.M.A.R.T. (vereinfacht)
 */

#define _POSIX_C_SOURCE 199309L

#include "hw_interrupts.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/sysinfo.h>
#include <sys/statvfs.h>
#include <time.h>
#include <errno.h>

/* ======================================================================
 * Speicher-Informationen
 * ====================================================================== */

int get_memory_info(MemoryInfo *info) {
    struct sysinfo si;
    if (sysinfo(&si) != 0) {
        return -1;
    }

    info->total_mb   = (si.totalram * si.mem_unit) / (1024 * 1024);
    info->free_mb    = (si.freeram * si.mem_unit) / (1024 * 1024);
    info->used_mb    = info->total_mb - info->free_mb;
    info->shared_mb  = (si.sharedram * si.mem_unit) / (1024 * 1024);
    info->buffer_mb  = (si.bufferram * si.mem_unit) / (1024 * 1024);
    info->swap_total = (si.totalswap * si.mem_unit) / (1024 * 1024);
    info->swap_free  = (si.freeswap * si.mem_unit) / (1024 * 1024);
    info->uptime_sec = si.uptime;
    info->procs      = si.procs;

    return 0;
}

/* ======================================================================
 * CPU-Informationen
 * ====================================================================== */

int get_cpu_count(void) {
    return sysconf(_SC_NPROCESSORS_ONLN);
}

int get_cpu_info(int core_id, CpuInfo *info) {
    char path[256];
    FILE *f;

    info->core_id = core_id;
    info->online = 1;
    info->temperature_mc = -1;
    info->frequency_khz = 0;

    /* CPU-Frequenz lesen */
    snprintf(path, sizeof(path),
             "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq", core_id);
    f = fopen(path, "r");
    if (f) {
        if (fscanf(f, "%lu", &info->frequency_khz) != 1) {
            info->frequency_khz = 0;
        }
        fclose(f);
    }

    /* CPU-Online-Status */
    if (core_id > 0) {  /* Core 0 ist immer online */
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpu%d/online", core_id);
        f = fopen(path, "r");
        if (f) {
            int val = 1;
            if (fscanf(f, "%d", &val) == 1) {
                info->online = val;
            }
            fclose(f);
        }
    }

    /* Temperatur aus thermal_zone lesen */
    for (int zone = 0; zone < 20; zone++) {
        snprintf(path, sizeof(path),
                 "/sys/class/thermal/thermal_zone%d/temp", zone);
        f = fopen(path, "r");
        if (f) {
            long temp_mc;
            if (fscanf(f, "%ld", &temp_mc) == 1) {
                if (info->temperature_mc < 0 || temp_mc > info->temperature_mc) {
                    info->temperature_mc = temp_mc;
                }
            }
            fclose(f);
            break;  /* Erste Zone reicht als Annäherung */
        }
    }

    return 0;
}

/* ======================================================================
 * Disk-Informationen
 * ====================================================================== */

int get_disk_info(const char *mount_point, DiskInfo *info) {
    struct statvfs sv;

    if (statvfs(mount_point, &sv) != 0) {
        return -1;
    }

    strncpy(info->mount_point, mount_point, sizeof(info->mount_point) - 1);
    info->mount_point[sizeof(info->mount_point) - 1] = '\0';

    info->total_bytes = (unsigned long long)sv.f_blocks * sv.f_frsize;
    info->free_bytes  = (unsigned long long)sv.f_bfree * sv.f_frsize;
    info->avail_bytes = (unsigned long long)sv.f_bavail * sv.f_frsize;
    info->used_bytes  = info->total_bytes - info->free_bytes;

    if (info->total_bytes > 0) {
        info->usage_percent = (double)info->used_bytes / info->total_bytes * 100.0;
    } else {
        info->usage_percent = 0.0;
    }

    return 0;
}

/* ======================================================================
 * Interrupt-Zählung
 * ====================================================================== */

long get_interrupt_count(void) {
    FILE *f = fopen("/proc/interrupts", "r");
    if (!f) return -1;

    long total = 0;
    char line[1024];

    /* Erste Zeile überspringen (Header) */
    if (fgets(line, sizeof(line), f) == NULL) {
        fclose(f);
        return -1;
    }

    while (fgets(line, sizeof(line), f)) {
        char *ptr = line;
        /* Interrupt-Nummer überspringen */
        while (*ptr == ' ') ptr++;
        while (*ptr && *ptr != ' ' && *ptr != ':') ptr++;
        if (*ptr == ':') ptr++;

        /* Alle CPU-Zähler aufsummieren */
        while (*ptr) {
            while (*ptr == ' ') ptr++;
            if (*ptr >= '0' && *ptr <= '9') {
                total += strtol(ptr, &ptr, 10);
            } else {
                break;
            }
        }
    }

    fclose(f);
    return total;
}

/* ======================================================================
 * System-Uptime
 * ====================================================================== */

double get_uptime_seconds(void) {
    FILE *f = fopen("/proc/uptime", "r");
    if (!f) return -1.0;

    double uptime = 0.0;
    if (fscanf(f, "%lf", &uptime) != 1) {
        uptime = -1.0;
    }
    fclose(f);
    return uptime;
}

/* ======================================================================
 * Zeitstempel (Nanosekunden-Präzision)
 * ====================================================================== */

long long get_timestamp_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}
