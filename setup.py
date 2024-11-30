from setuptools import setup, find_packages
setup(
name="connection-manager",
version="0.1.0",
packages=find_packages(where="src"),
package_dir={"": "src"},
install_requires=[
"typer>=0.12.0",
"rich>=13.0.0",
"inquirerpy>=0.3.4",
"requests>=2.25.0"
],
python_requires=">=3.8",
)
