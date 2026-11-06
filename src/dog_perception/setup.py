from setuptools import find_packages, setup
from glob import glob
package_name = 'dog_perception'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (f'share/{package_name}/config', glob('config/*')),

    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='holly',
    maintainer_email='3228828366@qq.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'pcd_publisher = dog_perception.pcd_publisher:main',
            'cloud_preprocess = dog_perception.cloud_preprocess:main',
        ],
    },
)
