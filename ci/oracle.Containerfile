# The oracle image: the reference emulator and the second black box, run only
# as binaries, on Ubuntu 24.04 by digest with its packages from the Ubuntu
# snapshot archive at one instant. warren-oracle.toml binds the base, the
# instant, the package list and each oracle binary's digest.
FROM docker.io/library/ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
ARG SNAPSHOT=20261101T000000Z
ARG BUILD_CPUS=0
ENV DEBIAN_FRONTEND=noninteractive
RUN taskset -c "$BUILD_CPUS" sh -eu -c '\
    apt="apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30"; \
    $apt update; $apt install -y --no-install-recommends ca-certificates; \
    sed -i -e "s#http://archive.ubuntu.com/ubuntu/#https://snapshot.ubuntu.com/ubuntu/${SNAPSHOT}/#" \
           -e "s#http://security.ubuntu.com/ubuntu/#https://snapshot.ubuntu.com/ubuntu/${SNAPSHOT}/#" \
           /etc/apt/sources.list.d/ubuntu.sources; \
    $apt update; \
    $apt install -y --no-install-recommends --allow-downgrades \
        xterm xvfb xfonts-base tmux ncurses-bin ncurses-term \
        python3 curl git gcc libc6-dev procps util-linux; \
    rm -rf /var/lib/apt/lists/*; \
    dpkg-query -W -f "\${Package}=\${Version}\n" | sort > /opt/oracle-packages.txt; \
    for tool in xterm tmux Xvfb infocmp; do \
        path=$(readlink -f "$(command -v "$tool")"); \
        case $tool in xterm) version=$(xterm -version) ;; tmux) version=$(tmux -V) ;; \
            Xvfb) version=$(dpkg-query -W -f "xvfb \${Version}" xvfb) ;; \
            infocmp) version=$(infocmp -V) ;; esac; \
        echo "$tool|$version|$(sha256sum "$path" | cut -d" " -f1)|$path"; \
    done > /opt/oracle-binaries.txt'
ENV LC_ALL=C.UTF-8
WORKDIR /work
