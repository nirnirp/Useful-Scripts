import wmi
import subprocess

# Connect to the WMI namespace
c = wmi.WMI()

# Create a management event watcher to monitor the Win32_PowerManagementEvent event
watcher = c.Win32_PowerManagementEvent.watch_for()

while True:
    print("Listening to sleep event.")
    
    # Wait for the event to occur
    event = watcher()

    # Check if the event is a sleep event
    if event.EventType == 4:
        print("Sleep detected. Running command.")
        # Run the command using PowerShell
        subprocess.run(["powershell", "-Command", "wsl minikube stop"])
