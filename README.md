# Setting Up a Virtual Environment and Running Pre-commit Hooks

## Step 1: Create and Activate a Virtual Environment

To isolate your project's dependencies, create and activate a virtual environment using Python's built-in `venv`:

```bash
# Create a virtual environment named "myenv"
python3 -m venv env

# Activate the virtual environment
source env/bin/activate

```

## Step 2: Install requirements

Next, install requirements and requirements-dev.

```bash
# Ensure you are inside the activated virtual environment
# Install requirements using pip
pip install -r requirements-dev.txt requirements.txt
```

## Step 3: Install the Hooks

Install the pre-commit hooks defined in your configuration:

```bash
pre-commit install
```

## Step 4: Run the Hooks

The pre-commit hooks will now run automatically when you attempt to commit changes. To run the hooks manually, use the following command:

```bash
pre-commit run --all-files
```

This will execute the configured hooks on all files in the repository.

Now, whenever you attempt to commit changes, the `nbqa` hooks will be triggered, ensuring consistent formatting and code quality.
```
