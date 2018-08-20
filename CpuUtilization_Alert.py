import boto3
import sys
import datetime
import json
import time
import smtplib
import commands
import logging
import tempfile


yesterday = datetime.datetime.now() - datetime.timedelta(days = 1)
yesterday_beginning = datetime.datetime(yesterday.year, yesterday.month, yesterday.day,0,0,0,0)
yesterday_beginning_time = int(time.mktime(yesterday_beginning.timetuple()))
yesterday_end = datetime.datetime(yesterday.year, yesterday.month, yesterday.day,23,59,59,999)
yesterday_end_time = int(time.mktime(yesterday_end.timetuple()))


def GetRegions():
    client = boto3.client('ec2')
    regions = [region['RegionName'] for region in client.describe_regions()['Regions']]
    return regions  ########array of regions############


def getEC2InstanceID(RegionName):
    session = boto3.Session(region_name = RegionName)
    ec2 = session.resource('ec2')
    instance_id= [instance.id for instance in ec2.instances.all()]
    if(len(instance_id)==0):
        return("no EC2Instances")
    else:
        return instance_id  ##########array of ec2 instanceID##########


def getRDSDBInstance(RegionName):
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            elif isinstance(obj, datetime.date):
                return obj.isoformat()
            elif isinstance(obj, datetime.timedelta):
                return (datetime.datetime.min + obj).time().isoformat()
            else:
                return super(DateTimeEncoder, self).default(obj)

    rds_client = boto3.client('rds', RegionName)
    db_instance_info = rds_client.describe_db_instances()
    output = json.dumps(db_instance_info,cls= DateTimeEncoder)
    jsonObject = json.loads(output)
    jsonarray = jsonObject['DBInstances']
    DBinstance_value = [key['DBInstanceIdentifier'] for key in jsonarray]
    if(len(DBinstance_value) == 0):
        return ("no DBInstances")
    else:
        return DBinstance_value    ##########array of dbinstance values##########

def RDS_Average_Utilization(InstanceValue,RegionName):
    global client,yesterday_beginning_time,yesterday_end_time
    session = boto3.Session(profile_name='default')
    cloudwatch = session.client('cloudwatch', region_name=RegionName)
    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/RDS',
        MetricName='CPUUtilization',
        Dimensions=[
            {
                'Name': 'DBInstanceIdentifier',
                'Value': InstanceValue
            },
        ],
        StartTime=yesterday_beginning_time,
        EndTime=yesterday_end_time,
        Period=120,
        Statistics=[
            'Average',
        ],
        Unit='Percent'
    )
    # print(response)
    if (response['Datapoints']== []):
        print('Empty Datapoints')
    else:
        for cpu in response['Datapoints']:
            if 'Average' in cpu:
                print(cpu['Average'])
                EmailBody = 'CPUUtilization above 80% for '+ InstanceValue + ' under region: '+ RegionName
                if (cpu['Average']>=80):
                    sendALERTEmail('SENDER_EMAIL', 'CPUUtilization Alert for RDS', EmailBody, 'RECEIVER_EMAIL')  ##### change sender and recipent here#######



def EC2_Average_Utilization(InstanceID, RegionName):
    session = boto3.Session(profile_name='default')
    cloudwatch = session.client('cloudwatch', region_name=RegionName)
    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2',
        MetricName='CPUUtilization',
        Dimensions=[
            {
                'Name': 'InstanceId',
                'Value': InstanceID
            },
        ],
        StartTime=yesterday_beginning_time,
        EndTime=yesterday_end_time,
        Period=120,
        Statistics=[
            'Average',
        ],
        Unit='Percent'
    )
    # print(response)
    if (response['Datapoints']== []):
        print('Empty Datapoints')
    else:
        for cpu in response['Datapoints']:
            if 'Average' in cpu:
                print(cpu['Average'])
                EmailBody = 'CPUUtilization above 80% for '+ InstanceID + ' under region: '+ RegionName
                if (cpu['Average']>=80):
                    sendALERTEmail('SENDER_EMAIL', 'CPUUtilization Alert for EC2', EmailBody, 'RECEIVER_EMAIL')  ##### change sender and recipent here#######


def sendALERTEmail(mail_sender, mail_subject, mail_content, mail_receiver):
     message_dict = { 'Data':
     'From: ' + mail_sender + '\n'
     'To: ' + mail_receiver + '\n'
     'Subject: ' + mail_subject + '\n'
     'MIME-Version: 1.0\n'
     'Content-Type: text/html;\n\n' +
     mail_content}
     try:
       _, message_dict_filename = tempfile.mkstemp()
       f = open(message_dict_filename,'w')
       f.write(json.dumps(message_dict))
     except IOError as e:
       logging.error(str(e))
       sys.exit(1)
     finally:
       f.close()
     aws_send_email_cmd = [
         'aws', 'ses', 'send-raw-email', '--region=us-east-1',
         '--raw-message=file://%s' % message_dict_filename]
     result = commands.getstatusoutput(' '.join(aws_send_email_cmd))
     logging.info('Sending message with subject "%s", result:%s.', mail_subject,
         result)
     if result[0] != 0:
       logging.error('Mail sending failed. Command: %s',
           ' '.join(aws_send_email_cmd))
     print('The Alert E-mail was sent successfully')



#################################################################################
################################################################################

def main():
    regions= GetRegions()
    for i in range(len(regions)):
        print(regions[i])
        instance_id = getEC2InstanceID(regions[i])
        print(instance_id)
        if (type(instance_id)==list):
            for j in range(len(instance_id)):
                print(instance_id[j])
                print ("For InstanceID "+ instance_id[j] +  ":")
                EC2_Average_Utilization(instance_id[j], regions[i])
        DBInstance_value = getRDSDBInstance(regions[i])
        print(DBInstance_value)
        if (type(DBInstance_value)==list):
            for j in range(len(DBInstance_value)):
                print ("For DBinstance "+ DBInstance_value[j] +  ":")
                RDS_Average_Utilization(DBInstance_value[j],regions[i])

if __name__ == "__main__":
    main()
