PODMAN_COMPOSE_CMD := $(shell command -v podman-compose 2> /dev/null)
CONTAINER_CMD := podman-compose

ifndef PODMAN_COMPOSE_CMD
	CONTAINER_CMD := docker-compose
endif

.PHONY:help
help: ##@ Print listing of key targets with their descriptions.
	@awk 'BEGIN {FS = ":.*##@"; printf "Usage:\n  make [command]\033[36m\033[0m\n\nAvailable commands:\n"} /^[$$()% a-zA-Z_-]+:.*?##@/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY:build-container
build-container: ##@ Build the container image.
	$(CONTAINER_CMD) build

.PHONY:clean-container
clean-container: ##@ Delete the container image.
	$(CONTAINER_CMD) down

PHONY:start
start: ##@ Run the container image for production.
	$(CONTAINER_CMD) up -d

PHONY:stop
stop: ##@ Stop the container image for production.
	$(CONTAINER_CMD) stop

PHONY:test
test: ##@ Run the container image for testing.
	$(CONTAINER_CMD) up