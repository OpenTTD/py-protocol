import setuptools
import version

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="openttd-protocol",
    version=version.get_version(),
    author="OpenTTD Dev Team",
    author_email="info@openttd.org",
    description="OpenTTD network protocol for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/OpenTTD/py-protocol",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
    install_requires=[
    ],
)
