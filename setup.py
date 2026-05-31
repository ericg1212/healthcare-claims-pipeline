from setuptools import setup, find_packages

setup(
    name="healthcare-claims-pipeline",
    version="0.1.0",
    packages=find_packages(exclude=["tests*", ".venv*"]),
)
