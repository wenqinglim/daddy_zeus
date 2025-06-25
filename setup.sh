#!/usr/bin/env bash
set -e

# --- CONFIG ---
PYTHON_VERSION=3.11.9
VENV_NAME=daddy_zeus_env

# --- FUNCTIONS ---
function info() {
  echo -e "\033[1;34m[INFO]\033[0m $1"
}
function error() {
  echo -e "\033[1;31m[ERROR]\033[0m $1" >&2
}

# --- CHECK PYENV ---
if ! command -v pyenv >/dev/null 2>&1; then
  info "pyenv not found. Installing pyenv..."
  curl https://pyenv.run | bash
  export PATH="$HOME/.pyenv/bin:$PATH"
  eval "$(pyenv init -)"
  eval "$(pyenv virtualenv-init -)"
else
  info "pyenv found."
fi

# --- INSTALL PYTHON ---
if ! pyenv versions --bare | grep -q "^$PYTHON_VERSION$"; then
  info "Installing Python $PYTHON_VERSION with pyenv..."
  pyenv install $PYTHON_VERSION
else
  info "Python $PYTHON_VERSION already installed."
fi

# --- CREATE VIRTUALENV ---
if ! pyenv virtualenvs --bare | grep -q "^$VENV_NAME$"; then
  info "Creating virtualenv $VENV_NAME..."
  pyenv virtualenv $PYTHON_VERSION $VENV_NAME
else
  info "Virtualenv $VENV_NAME already exists."
fi

info "Activating virtualenv $VENV_NAME..."
export PYENV_VERSION=$VENV_NAME

# --- INSTALL UV ---
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv (universal virtualenv)..."
  pip install --upgrade pip
  pip install uv
else
  info "uv already installed."
fi

# --- INSTALL REQUIREMENTS ---
if [ -f "pyproject.toml" ]; then
  info "Installing dependencies from pyproject.toml using uv..."
  uv sync --dev
else
  error "No pyproject.toml found!"
  exit 1
fi

# --- ENABLE PRE-COMMIT HOOKS ---
info "Enabling git hooks..."
pre-commit install

info "Setup complete!"
echo "To activate your environment in the future, run:"
echo "  pyenv activate $VENV_NAME" 