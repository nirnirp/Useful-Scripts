# File Merge Script

This shell script allows you to merge the textual content of multiple files or a whole folder into a single file. Each file's content is separated by three empty lines, and a header is added before each file's content, displaying the file name and the number of rows copied into the new file.

## Usage

1. Make the script executable by running the following command in the terminal:

```bash
chmod +x merge_files.sh
```
Run the script using the following command:

```bash
./merge_files.sh [file1.txt file2.txt folder/]
```
You can provide multiple file names or a folder as arguments, separated by spaces.
If you provide a folder as an argument, the script will process all files within that folder.
Invalid arguments will be ignored.

After running the script, a new file named output.txt will be created in the same directory. It will contain the merged content of the specified files, with each file's content separated by three empty lines. Each file's content will be preceded by a header displaying the file name and the number of rows copied into the new file.
