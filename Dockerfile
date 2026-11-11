# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.12-windowsservercore-1809

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1
RUN powershell -Command "Invoke-WebRequest -Uri 'https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe' -OutFile 'C:/git.exe'; Start-Process 'C:/git.exe' -ArgumentList '/VERYSILENT','/NORESTART','/NOCANCEL','/SP-' -Wait; Remove-Item 'C:/git.exe' -Force"
WORKDIR /app
COPY . /app

RUN python -m pip install --no-cache-dir ./cube
RUN pip uninstall -y opencv-python 
RUN pip install --no-cache-dir opencv-python-headless

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "-m", "cube", "--cli"]
