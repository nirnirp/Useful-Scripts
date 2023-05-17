#!/bin/bash

# Check if the input is provided
if [ $# -eq 0 ]; then
  echo "Please provide file(s) or folder as argument(s)."
  exit 1
fi

# Function to process a single file
process_file() {
  local file="$1"
  local filename="$(basename "$file")"

  # Count the number of lines in the file
  local num_lines=$(wc -l < "$file")

  # Output the header
  echo "-> File: $filename ($num_lines rows)" >> output.txt

  # Output the file content
  cat "$file" >> output.txt

  # Add three empty lines after the file content
  echo -e "\n\n" >> output.txt
}

# Create a new file for the output
echo "" > output.txt

# Process each argument (file or folder)
for arg in "$@"; do
  if [ -d "$arg" ]; then
    # Argument is a folder, process all files in the folder
    for file in "$arg"/*; do
      [ -f "$file" ] && process_file "$file"
    done
  elif [ -f "$arg" ]; then
    # Argument is a file, process the file
    process_file "$arg"
  else
    echo "Invalid argument: $arg"
  fi
done

echo "Output file created: output.txt"
