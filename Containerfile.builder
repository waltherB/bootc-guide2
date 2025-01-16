# Containerfile.builder
FROM registry.access.redhat.com/ubi9/python-39:latest

USER root

# Register and attach using activation key
ENV ACTIVATION_KEY=development-activation-key
ENV ORG=5668801
RUN subscription-manager register --activationkey ${ACTIVATION_KEY} --org ${ORG}
# Clean up
RUN rm -rf /root/.rhsm


# Install EPEL repository
RUN dnf install -y \
    https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm \
    && dnf clean all

# Install required packages
RUN dnf install -y --nobest --allowerasing \
    podman \
    buildah \
    skopeo \
    bootc \
    git \
    curl \
    fuse-overlayfs \
    container-selinux \
    slirp4netns \
    && dnf clean all

# Configure podman for rootless operation
RUN echo 'podman:165536:65536' >> /etc/subuid && \
    echo 'podman:165536:65536' >> /etc/subgid

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the guide script and utilities
COPY guide.py /app/

WORKDIR /workspace

CMD ["python", "/app/guide.py"]
