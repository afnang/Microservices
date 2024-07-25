# Flask App Setup Instructions

## Prerequisites

Before running the Flask app, please ensure the following:

1. **Environment Variable**: Set the `FBASE` environment variable in your local environment. This is crucial for the program to function. You can set this variable using the `export` command on Unix-based systems or the `set` command on Windows.

2. **Python Version**: Ensure you have Python 3.6 or higher installed.

3. **Dependencies**: Install the required Python packages using `pip`:
    ```sh
    pip install flask requests
    ```

## Running the Program

To run the program, use the following command:
```sh
python sc.py -r <database_type>