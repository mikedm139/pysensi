from setuptools import setup


setup(
    name='pysensi',
    version='0.1',
    url='https://github.com/mikedm139/pysensi',
    packages=['pysensi'],
    license='MIT Software License',
    author='Mike Meier based on the work of Steve Bate and Jared Harley',
    install_requires=[
                    "certifi >= 2018.4.16",
                    "chardet >= 3.0.4",
                    "decorator >= 4.3.0",
                    "idna >= 2.6",
                    "jsonpath-rw >= 1.4.0",
                    "pkg-resources >= 0.0.0",
                    "ply >= 3.11",
                    "requests >= 2.18.4",
                    "six >= 1.11.0",
                    "urllib3 >=1.22"
                    ],
    author_email='mike.d.meier@gmail.com',
    description='Python library for interacting with Emerson Sensi WiFi thermostats',
    long_description=open('README.md').read()
)
