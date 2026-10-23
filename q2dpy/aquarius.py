"""Contains code for pulling current discharge from specified gage site"""

import datetime as dt

import requests

SERVER_NAME = 'dnrhln6386.state.mt.ads'
USER_NAME = '****'
PASSWORD = '****'
aveID = 'a81b273b22fa4de0bd0954a39dd2ada4'
instID = 'f449c1fa98f4486895af43af618c7eeb'
#  Directory not used, could pull id from csv by location id
DIRECTORY = r'\\DNRHLN6386.state.mt.ads\Fileshare$\Aquarius_Alarms\WSB'


def format_timestamp(time):
    if time == 0:
        return 0
    else:
        try:
            tf = dt.datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%f0%z") - dt.timedelta(hours=6)
            tf = tf.strftime("%b-%d %H:%M")
            return tf
        except ValueError:
            time_list = list(time.strip(""))
            time_list[12] = "3"
            time = ''.join(time_list)
            tf = dt.datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%f0%z") - dt.timedelta(hours=5)
            tf = tf.strftime("%b-%d %H:%M")
            return tf


def get_site_Q():
    id_list = [instID, aveID]

    tmin = dt.datetime.utcnow() - dt.timedelta(minutes=1440)
    tmin = tmin.strftime(f"%Y-%m-%dT%H:%M:%SZ")

    t_now = dt.datetime.utcnow()
    t_now = t_now.strftime(f"%Y-%m-%dT%H:%M:%SZ")

    t_now_format = dt.datetime.now()
    t_now_format = t_now_format.strftime(f"%b %d, %Y")

    # # Outputs csv of sensor data anomalies based on reference to master sensor list csv # #

    print("Acquiring StAGE data...")
    site_data = []
    for i in id_list:
        aq_params = {'TimeSeriesUniqueId': i,
                     'QueryFrom': tmin,
                     'QueryTo': t_now}
        response = requests.get(
            url=f'http://{SERVER_NAME}/AQUARIUS/Publish/v2/GetTimeSeriesCorrectedData',
            auth=(USER_NAME, PASSWORD),
            params=aq_params)
        response.raise_for_status()
        series_data = response.json()
        # print(json.dumps(series_data, indent=4))
        try:
            timestamp = series_data["Points"][-1]["Timestamp"]
        except IndexError:
            timestamp = 0
        try:
            value = series_data["Points"][-1]["Value"]["Numeric"]
        except IndexError:
            value = 0
        point_dict = {
            "UniqueId": series_data["UniqueId"],
            "LocationIdentifier": series_data["LocationIdentifier"],
            "Parameter": series_data["Parameter"],
            "Timestamp": format_timestamp(timestamp),
            "Value": value,
            "Unit": series_data["Unit"]
        }
        site_data.append(point_dict["Value"])

    if site_data[0] > 0:
        q_val = round(site_data[0] * 0.02832, 3)
    else:
        if site_data[1] > 0:
            q_val = round(site_data[1] * 0.02832, 3)
        else:
            q_val = 0

    return q_val
