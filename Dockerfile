# Use the official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port FastAPI will run on
EXPOSE 8080

# Command to run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
