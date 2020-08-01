#!/usr/bin/env python
import json
import queue
import threading
import time

import boto3
import redis
import requests
import yaml
from botocore.exceptions import ClientError, BotoCoreError
from flask import Flask
from flask import jsonify
import uuid

import hashlib

# Read parameters from config file
with open("config.yml", "r") as ymlfile:
    cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
serverAddress = cfg['Server']['Address']
serverPort = cfg['Server']['Port']
dynamoDBKey = cfg['DynamoDB']['PrimaryPartitionKey']
dynamoDBTable = cfg['DynamoDB']['TableName']
dynamoDBRegion = cfg['DynamoDB']['Region']
redisHost = cfg['Redis']['Host']
redisPort = cfg['Redis']['Port']
boto3Region = cfg['Boto3']['Region']
redisTimeout = 5

"""Simple requests queue
We should use only PutQueue() and GetTrottling() functions.
"""
SleepTimePerRequest = 10  # Value for increasing queue per request
QueueSizeForThrottling = 10  # If queue size bigger than variable, then requests will be throttled
QueueSizeLimit = 20 #Don't inscrease queue, if queue size equal to
SleepQueue = queue.Queue()


# Worker for queue
def worker():
    while True:
        item = SleepQueue.get()
        print(f'Working on {item}, queue size: {SleepQueue.qsize()}')
        time.sleep(item)
        print(f'Finished {item}, queue size: {SleepQueue.qsize()}')
        SleepQueue.task_done()


threading.Thread(target=worker, daemon=True).start()

# Put item into queue
def PutQueue(time=SleepTimePerRequest):
    if(QueueSize()>=QueueSizeLimit):
        return
    SleepQueue.put(time)


# Check throttling status function
def GetTrottling():
    if (SleepQueue.qsize() > 10):
        return True
    else:
        return False


# Count items in queue
def QueueSize():
    return SleepQueue.qsize()


def GetInstanceID():
    try:
        response = requests.get('http://169.254.169.254/latest/meta-data/instance-id')
        return response.text
    except requests.exceptions.ConnectionError as e:
        print(e)
        return 'not instance'

# CallerID for status
def GetCallerID():
    try:
        client = boto3.client('sts', region_name=boto3Region)
        return client.get_caller_identity()
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}

# Сheck DynamoDB connection
def checkDynamoDB():
    try:
        recordid = str(uuid.uuid4())
        ddb = boto3.resource('dynamodb', region_name=dynamoDBRegion)
        table = ddb.Table(dynamoDBTable)
        response = table.put_item(
            Item={
                dynamoDBKey: recordid
            })
        response = table.get_item(
            Key={
                dynamoDBKey: recordid
            }
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
        return False
    except BotoCoreError as e:
        print(e.fmt)
        return False
    else:
        item = response['Item']
        print("GetItem succeeded:")
        print(json.dumps(item))
        return True


# Check Redis connection
def checkRedis():
    try:
        r = redis.Redis(host=redisHost, port=redisPort, db=0, socket_connect_timeout=redisTimeout)
        if (r.set('foo', 'bar')):
            return True
        else:
            return False
    except redis.exceptions.RedisError as e:
        print(e)
        return False


# AutoScaling groups for status
def DescribeAutoScalingGroups():
    try:
        client = boto3.client('autoscaling', region_name=boto3Region)
        return client.describe_auto_scaling_groups()
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}


# LoadBalncer for status
def DescribeLoadBalancers():
    try:
        client = boto3.client('elbv2', region_name=boto3Region)
        return client.describe_load_balancers()
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}

# Listeners for status
def DescribeListeners():
    try:
        client = boto3.client('elbv2', region_name=boto3Region)
        lbrs = client.describe_load_balancers()['LoadBalancers']
        res = []
        for lbr in lbrs:
            res.append(client.describe_listeners(LoadBalancerArn=lbr['LoadBalancerArn']))
        return res
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}

# Target groups for status
def DescribeTargetGroups():
    try:
        client = boto3.client('elbv2', region_name=boto3Region)
        return client.describe_target_groups()
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}


# DynamoDB Tables for status
def DescribeTables():
    try:
        client = boto3.client('dynamodb', region_name=boto3Region)
        tables = client.list_tables()['TableNames']
        res = []
        for t in tables:
            res.append(client.describe_table(TableName=t))
        return res
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}


# Redis Clusters for status
def DescribeRedisClusters():
    try:
        client = boto3.client('elasticache', region_name=boto3Region)
        return client.describe_cache_clusters()
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}

# ECS Services for status
def DescribeECSService():
    try:
        client = boto3.client('ecs', region_name=boto3Region)
        clstrs = client.list_clusters()['clusterArns']
        result = []
        for v in clstrs:
            result.append(client.list_services(cluster=v))
        return result
    except BotoCoreError as e:
        print(e.fmt)
        return {}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}
instanceID = GetInstanceID()
app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello, competitor! <br/> \
        See <a href=/status> status </a> for a self check."


#SelfCHeck page
@app.route("/status")
def Status():
    resp = {
        'Healthy': GetTrottling(),
        'QueueSize': QueueSize(),
        'InstanceID': instanceID,
        'Redis': {
            'Host': redisHost,
            'Port': redisPort,
            'RedisConnection': checkRedis(),
        },
        'DynamoDB': {
            'Region': dynamoDBRegion,
            'TableName': dynamoDBTable,
            'PrimaryPartitionKey': dynamoDBKey,
            'DynamoDBConnection': checkDynamoDB()
        },
    }
    return jsonify(resp)


#request for get full response about infrastructure
@app.route("/full-status")
def FullStatus():
    resp = {
        'Healthy': GetTrottling(),
        'QueueSize': QueueSize(),
        'InstanceID': instanceID,
        'Redis': {
            'Host': redisHost,
            'Port': redisPort,
            'RedisConnection': checkRedis(),
        },
        'DynamoDB': {
            'Region': dynamoDBRegion,
            'TableName': dynamoDBTable,
            'PrimaryPartitionKey': dynamoDBKey,
            'DynamoDBConnection': checkDynamoDB()
        },
        'AutoScalingGroup': DescribeAutoScalingGroups(),
        'LoadBalancer':DescribeLoadBalancers(),
        'ECS-services':DescribeECSService(),
        'Listeners': DescribeListeners(),
        'TargetGroups': DescribeTargetGroups(),
        'CacheClusters': DescribeRedisClusters(),
        'CallerID': GetCallerID(),
        'DynamoDBTables': DescribeTables()
    }
    return jsonify(resp)


@app.route("/load")
def Load():
    PutQueue()
    message = f"Test request accepted; Queue size: {str(QueueSize())} "
    if (GetTrottling()):
        #time.sleep(1)
        message += "Code 500"
        return message, 500
    # Write content as utf-8 data
    return message


@app.route("/health")
def Health():
    if (GetTrottling()):
        return "unhealthy", 500
    else:
        return "healthy"

#add Integrity header for checking code integrity
@app.after_request
def apply_caching(response):
    response.headers["Integrity"] = integrity
    return response

integrity = hashlib.md5(open('server.py','rb').read()).hexdigest()

print(f'InstanceID: {instanceID}')
if __name__ == '__main__':
    app.run(host=serverAddress, port=serverPort)
