# 1. Base image
FROM python:3.10

# 2. Set working directory
WORKDIR /app

# 3. Copy requirements file
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy project files
COPY . .

# 6. Expose port
EXPOSE 5000

# 7. Run the application
CMD ["python", "app.py"]