# P2P 2G chat
This is a python program that emulate 2G(Second Generation) mobile communications.
It can simulate the process of making and receiving calls. Because of we don't have a real 2G base
station, so I use socket point to point to transmit voice package.
### execute this project
run Python virtual environment(optional)

```bash
pip3 install virtualenv
virtualenv ven #alter any name you want
# Windows
./ven/Script/activate
# linux
source ven/bin/activate
```

install all package

```bash
pip install -r requirements.txt
```
compile package
```bash
python setup.py build_ext --inplace
```
Run it. Open two CLI can communicate via local-loopback(remember port number have to match).
```bash
python main.py
```