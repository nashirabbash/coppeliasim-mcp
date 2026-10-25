FROM ros:humble-ros-base-jammy

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ros-humble-image-transport \
    ros-humble-tf2-ros \
    ros-humble-example-interfaces \
    ros-humble-demo-nodes-cpp \
    ros-humble-action-tutorials-cpp \
    libgl1 \
    libsodium23 \
    python3-zmq \
    python3-cbor2 \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_DOMAIN_ID=0
