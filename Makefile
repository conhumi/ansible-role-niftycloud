
IMAGE_NAME := "niftycloud/ansible-role-niftycloud"

build:
	docker build -t ${IMAGE_NAME} .
test:
	make build
	docker run --workdir /work/library --rm -ti -v $(PWD):/work ${IMAGE_NAME} bash -c " \
          nosetests --no-byte-compile --with-coverage && \
          coverage report --include=./niftycloud*.py"
