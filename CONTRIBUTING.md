# Contributing Guidelines

Thank you for your interest in the Mistode project! We welcome contributions of all forms.

## Development Environment Setup

1. Clone the project:
   ```shell
   git clone https://github.com/for13to1/mistode.git
   cd mistode
   ```

2. Install development dependencies:
   ```shell
   pip install -e ".[dev]"
   ```

3. Run tests:
   ```shell
   pytest tests/ -v
   ```

## Code Standards

- Use Black to format code: `black src/ tests/`
- Use isort to sort imports: `isort src/ tests/`
- Use flake8 to check code quality: `flake8 src/ tests/`

## Submitting Code

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Commit changes: `git commit -m "Description of your changes"`
3. Push to remote: `git push origin feature/your-feature-name`
4. Create a Pull Request

## Reporting Issues

Please report bugs or suggest features in GitHub Issues, including:

- Issue description
- Reproduction steps
- Expected behavior
- Actual behavior
- Environment information

## Development Process

1. Ensure all tests pass
2. Add test cases for new features
3. Update documentation
4. Follow existing code style
