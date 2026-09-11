# Use an official Python runtime based on Alpine as a parent image
FROM python:3.9-alpine

# Set the image name and labels
LABEL maintainer="Sanyam Malik"
LABEL description="MockPlant"
LABEL image_name="mockplant"
LABEL tag="latest"

# Install git, cron, and other dependencies including Java 17, Node.js, kernel headers, and C++ compiler
RUN apk update && \
    apk add --no-cache git curl nano bash

# Set the working directory
WORKDIR /app

# Copy the entire current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set the PYTHONPATH to include the shared directory
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Copy entrypoint script
RUN chmod +x /app/entrypoint.sh

# Start flask server
CMD ["/app/entrypoint.sh"]