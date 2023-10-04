# Basic Structure: Run the Hooks
project_name/
│
├── .git/                         # Git repository and metadata
├── .gitignore                    # Gitignore file to specify ignored files and directories
├── README.md                     # Project README with an overview, setup, and usage instructions
├── requirements.txt              # File listing project dependencies
├── setup.py                      # Setup file for packaging and distribution
│   ├── src/                      # Source code directory
│   │   └── project_name/        # Python package directory
│   │       ├── __init__.py      # Package initialization file
│   │       ├── module1.py       # Module 1 source code
│   │       └── module2.py       # Module 2 source code
│   └── ...
├── tests/                        # Test directory
│   ├── test_module1.py          # Unit tests for module1
│   └── test_module2.py          # Unit tests for module2
├── docs/                         # Documentation directory (optional)
│   ├── index.md                  # Main documentation file
├── examples/                     # Directory for example usage of the project (optional)
├── notebooks/                    # Directory for Jupyter notebooks (optional)
└── scripts/                      # Directory for utility scripts (optional)


# Setting Up a Virtual Environment and Running Pre-commit Hooks

## Step 1: Create and Activate a Virtual Environment

To isolate your project's dependencies, create and activate a virtual environment using Python's built-in `venv`:

```bash
# Create a virtual environment named "myenv"
python3 -m venv env

# Activate the virtual environment
#For Linux/MacOs
source env/bin/activate

# For Windows
.\env\Scripts\activate

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

Now, whenever you attempt to commit changes, the hooks will be triggered, ensuring consistent formatting and code quality.
