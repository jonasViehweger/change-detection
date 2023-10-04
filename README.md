# Basic Project Structure

This is the basic structure of your repository

<pre>
project_name/
│
├── .gitignore                    # Gitignore file to specify ignored files and directories
├── gitlab-ci.yml                 # Basic GitLab CI file
├── pre-commit-config.yaml        # Basic pre-commit config file
├── pyproject.toml                # TOML configuration file often used for tool settings and project metadata
├── README.md                     # Project README with an overview, setup, and usage instructions
├── requirements.txt              # File listing project dependencies
├── requirements-dev.txt          # File listing project dependencies for development
├── data/                         # Directory with data archives; add files here and include in gitinore if needed (optional)
├── notebooks/                    # Directory for Jupyter notebooks (optional)
├── scripts/                      # Directory for Python scripts (optional)
└── env/                          # Your environment (This will be in gitignore)
</pre>

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
