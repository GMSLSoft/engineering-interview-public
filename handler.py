import boto3
import os
import json
import numpy
from datetime import datetime, timedelta


def schedule_refresh(asg, asg_name, refresh_time):

    response = asg.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name],
    )

    desired_capacity = int(
        response["AutoScalingGroups"][0]["DesiredCapacity"])

    if desired_capacity == 0:
        return False
    else: 
        time = datetime.strptime(refresh_time, "%H:%M")
        days_offset = 1 if time.hour < datetime.now().hour else 0
        tomorrow = datetime.today() + timedelta(days=days_offset)
        refresh_time = tomorrow.replace(
            hour=time.hour,
            minute=time.minute,
            second=0,
            microsecond=0)

        asg.put_scheduled_update_group_action(
            AutoScalingGroupName=asg_name,
            ScheduledActionName="Shutdown",
            StartTime=refresh_time,
            DesiredCapacity=0)

        asg.put_scheduled_update_group_action(
            AutoScalingGroupName=asg_name,
            ScheduledActionName="Startup",
            StartTime=refresh_time + timedelta(minutes=1),
            DesiredCapacity=1)

        return True

def lambda_handler(event, context):
    ami_type = os.environ['ami_type']
    ami_arch = os.environ['ami_arch']
    region = "eu-central-1" 

    images = json.loads(event["Records"][0]["Sns"]["Message"])["v1"]["Regions"]

    matchingImages = []
    for key in images: 
        if key == region:
            imageName = images[key]["name"] 
            if imageName.startswith(ami_type) and imageName.endswith(ami_arch):
                matchingImages.add(images[key]["ImageId"]) 

    ltid = os.environ["launch_template_id"] 
    asg_name = os.environ["asg_name"]
    refresh_time = os.environ['refresh_time']

    boto3.client("ec2").create_launch_template_version(
        LaunchTemplateId=ltid,
        SourceVersion="$Latest",
        LaunchTemplateData={"ImageId": matchingImages[0]}
    )

    response = boto3.client("ec2").modify_launch_template(
        LaunchTemplateId=ltid,
        DefaultVersion="$Latest"
    )

    latest_version = int(
        response["LaunchTemplate"]["LatestVersionNumber"])

    boto3.client("ec2").delete_launch_template_versions(
        LaunchTemplateId=ltid,
        Versions=[str(latest_version - 2)]
    )

    print("AMI updated. New AMI is " + matchingImages[0] + ".")

    is_refresh = schedule_refresh(
        boto3.client("autoscaling"),
        asg_name,
        refresh_time)

    if is_refresh:
        print("Refresh scheduled for " + refresh_time + ".")

testEvent = {
    "Records": [
        {
            "EventVersion": "1.0",
            "EventSubscriptionArn": "arn:aws:sns:us-east-1:137112412989:amazon-linux-2-ami-updates",
            "EventSource": "aws:sns",
            "Sns": {
                "Message": ""
            }
        }
    ]
}

message = {
    "v1": {
        "ReleaseVersion": "",
        "ImageVersion": "",
        "ReleaseNotes": "",
        "Regions": {
            "eu-central-1": [
                {
                    "Name": "amzn2-ami-hvm-2.0.20190508-arm64-gp2",
                    "ImageId": "ami-056343e91872518f7"
                }
            ]
        }
    }
}

testEvent["Records"][0]["Sns"]["Message"] = json.dumps(message)

lambda_handler(testEvent, "")
