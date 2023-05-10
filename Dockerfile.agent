FROM python:3.8-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port if your application uses one
# EXPOSE <port_number>

# Start the application
CMD ["python", "agent.py"]
