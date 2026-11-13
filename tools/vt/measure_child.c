/* Small native parent for wait4 resource measurement; no buffered input. */
#define _DEFAULT_SOURCE 1
#define _DARWIN_C_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static int64_t rss_bytes(const struct rusage *usage) {
#ifdef __APPLE__
    return (int64_t)usage->ru_maxrss;
#else
    return (int64_t)usage->ru_maxrss * 1024;
#endif
}

static int64_t nanoseconds(const struct timespec *value) {
    return (int64_t)value->tv_sec * 1000000000 + value->tv_nsec;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fputs("usage: measure-child PROGRAM [ARG ...]\n", stderr);
        return 2;
    }
    struct rusage parent, child, floor;
    struct timespec start, end;
    int channel[2];
    if (getrusage(RUSAGE_SELF, &parent) || clock_gettime(CLOCK_MONOTONIC, &start) || pipe(channel)) {
        perror("resource setup");
        return 2;
    }
    fflush(NULL);
    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        close(channel[0]);
        close(channel[1]);
        return 2;
    }
    if (pid == 0) {
        close(channel[0]);
        int64_t inherited = -1;
        if (getrusage(RUSAGE_SELF, &floor) == 0) inherited = rss_bytes(&floor);
        ssize_t sent = write(channel[1], &inherited, sizeof inherited);
        close(channel[1]);
        if (sent != (ssize_t)sizeof inherited) _exit(126);
        signal(SIGALRM, SIG_DFL);
        alarm(1800);
        execvp(argv[1], argv + 1);
        perror("exec");
        _exit(127);
    }
    close(channel[1]);
    int64_t inherited = -1;
    ssize_t received;
    do { received = read(channel[0], &inherited, sizeof inherited); } while (received < 0 && errno == EINTR);
    close(channel[0]);
    int status = 0;
    pid_t waited;
    do { waited = wait4(pid, &status, 0, &child); } while (waited < 0 && errno == EINTR);
    if (waited != pid || received != (ssize_t)sizeof inherited || clock_gettime(CLOCK_MONOTONIC, &end)) {
        perror("resource wait/read/clock");
        return 2;
    }
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    printf("MEASURE process exit=%d signal=%d wall-nanoseconds=%lld peak-rss-bytes=%lld child-before-exec-peak-rss-bytes=%lld parent-inherited-peak-rss-bytes=%lld limit-seconds=1800\n",
           code, WIFSIGNALED(status) ? WTERMSIG(status) : 0,
           (long long)(nanoseconds(&end) - nanoseconds(&start)), (long long)rss_bytes(&child),
           (long long)inherited, (long long)rss_bytes(&parent));
    return code;
}
