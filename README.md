# timus_api
A tool to access https://acm.timus.ru/ services programmatically

## How to install
### 1) from github:
`pip install git+https://github.com/dr-bright/timus_api`
### 2) from zip
`pip install timus_api-master.zip`

## Example uses:
```
python -m timus_api submit sourcecode.txt 1037 320816ZW cpp utf-8
```
```
python -m timus_api submit task1037.c - 320816ZW -
```
Try this to test if everything is working:
```
python -m timus_api submit "print(sum(map(int,input().split())))" 1000 320816ZW py utf-8
```