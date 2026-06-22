#!/bin/bash

# Script to fix 502 Bad Gateway caused by missing database tables in DMOJ

echo "Starting the fix process..."

# Navigate to the project directory
cd /home/agoj/site || { echo "Failed to navigate to project directory"; exit 1; }

# Activate the virtual environment
source /home/agoj/venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Run database migrations
echo "Running database migrations..."
python manage.py migrate || { echo "Database migration failed"; exit 1; }

# Restart the uWSGI backend server using supervisorctl
# Requires sudo/root privileges depending on your setup.
echo "Restarting the backend server..."
sudo supervisorctl restart site || { echo "Failed to restart supervisor site"; exit 1; }

echo "Fix completed successfully! The website should now be up and running."
