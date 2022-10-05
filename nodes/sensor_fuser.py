#!/usr/bin/env python3
import rospy
import numpy as np
from tel280_perception_pkg.helper import SimpleNavHelpers
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from message_filters import Subscriber, ApproximateTimeSynchronizer
import cv2
from cv_bridge import CvBridge, CvBridgeError
import math


class SensorFuserNode():
    
    def __init__(self):

        # Use ApproximateTimeSynchronizer to get synced sensor data
        atss = ApproximateTimeSynchronizer([Subscriber("/camera/rgb/image_raw", Image),
                                           Subscriber(
                                               "/camera/rgb/camera_info", CameraInfo),
                                           Subscriber("/scan", LaserScan)],
                                           queue_size=1, slop=0.1
                                           )
        atss.registerCallback(self.listener_callback)

        # 4 publishing laser scan projected image
        self.image_pub = rospy.Publisher("new", Image)

        # 4 converting sensor_msgs::Image -> opencv image
        self.bridge = CvBridge()

        # 4 Transforming laser points from LIDAR frame to camera frame
        self.helper = SimpleNavHelpers()

    def listener_callback(self, image: Image, camerainfo: CameraInfo, laser: LaserScan):

        rospy.loginfo(str("Recieved synced Image, CameraInfo, and LaserScan"))

        try:
            # convert sensor_msgs::Image -> opencv image
            cv_image = self.bridge.imgmsg_to_cv2(image, "bgr8")
        except CvBridgeError as e:
            # Let us know if it was a failure
            print(e)

        # Read and store Laserscan
        # convert to x, y, z
        curr_angle = 0.0
        points = []
        ranges = []
        for range in laser.ranges:
            curr_point = [.0, .0, .0]  # x, y, z
            curr_point[0] = range * math.cos(curr_angle)
            curr_point[1] = range * math.sin(curr_angle)
            curr_point[2] = 0  # z is zero since this is a 2D LIDAR

            # FOV of camera is limited in between -45 , +45 degrees
            # we wont project points that are behind camera
            if curr_point[0] < 0 or math.isnan(range):
                curr_angle += laser.angle_increment
                continue

            # Narrow down on the sides as well, camera wont see too far left and right
            if abs(curr_point[1]) > 2:
                curr_angle += laser.angle_increment
                continue
            # store the points and keep a copy of ranges
            points.append(curr_point)
            ranges.append(range)

            # increment the angle to convert next laser range to x, y
            curr_angle += laser.angle_increment

        # points are now in laser frame, but we wanna project them to image, the first thing
        # we do is to transfrom them to 3D camera frame (camera_rgb_optical_frame) and then to image plane
        # Below function will transform points from source(lidar) to target(camera) frames
        points_in_cam_frame = self.helper.transform_points(
            points=points,
            source_frame=laser.header.frame_id,
            target_frame=image.header.frame_id)

def main():

    rospy.init_node("SensorFuserNode")
    node = SensorFuserNode()
    rate = rospy.Rate(20)

    while not rospy.is_shutdown():
        rate.sleep()


if __name__ == '__main__':
    main()
