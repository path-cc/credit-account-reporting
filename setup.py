from setuptools import setup, find_packages

setup(
    name="cas_admin",
    version="2.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["click", "elasticsearch<8.0.0", "dnspython", "XlsxWriter<=3.2.2"],
    entry_points={
        "console_scripts": [
            "cas_admin = cas_admin.cli:cli",
        ],
    },
)
