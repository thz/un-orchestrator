#!/bin/sh
/usr/bin/cadvisor -logtostderr &
if [ -z ${NAME+x} ];
then cname=cadvproxy
else cname=$NAME
fi
if [ -z ${KEY+x} ];
then ckey=a
else ckey=$KEY
fi
<<<<<<< HEAD
/usr/bin/cadvisor -port=$cport -logtostderr &
while : ; do
  if curl --fail -X GET "127.0.0.1:$cport"; then
      break;
  fi
  echo "."
  sleep 1;
done
python3 main.py $cname /keys/$ckey -p $cport;
=======
python3 main.py $cname /keys/$ckey;
>>>>>>> 7cdaf2289eade2676ec1a0f2a61318b7d9e0c20a
