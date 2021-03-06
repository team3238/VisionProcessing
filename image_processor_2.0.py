#!/usr/bin/python
#Team3238 Cyborg Ferrets 2014 Object Detection Code
#Start with
#python image_processor.py 'path/to/image.jpg'
#don't pass an image argument to use the VideoCapture(0) stream.
# Video capture mode updates the frame to process every video_pause milliseconds, so adjust that.
#set enable_dashboard = True to send range and bearing over smart dashboard network_tables interface.
#set show_windows     = False for on-robot, no monitor processing on pandaboard.

#This code is a merge of vision_lib.py, bearing_formula.py, distance_formula.py and team341 java vision detection code from (2012?) competition.

#java -jar SmartDashboard ip 127.0.0.1, for example, will start the dashboard if running on this same host.
#Now tuned for green leds.
#expected camera settings (sorry no numbers on camera interface.)
# exposure -> far right
# gain -> far left
# brightness ~ 20% from left
# contrast ~ 20% from left
# color intensity ~ 18% from left


enable_dashboard = True
show_windows     = False

window_scale = 0.5
window_size = (int(640*window_scale), int(480*window_scale))

from cv2 import *
import numpy as np
import sys
import math
import commands

if enable_dashboard:
  from pynetworktables import *

if enable_dashboard:
  SmartDashboard.init()
#pretend the robot is on the network reporting its heading to the SmartDashboard,
#  then let the SmartDashboard user modify it and send it back to this code to simulate movement.
camera_exposure_title = 'Camera Exposure:'

class ImageProcessor:
  #all these values could be put into the SmartDashboard for live tuning as conditions change.

  default_shape   = (480,640,3)
  h               = np.zeros(default_shape, dtype=np.uint8)
  s               = np.zeros(default_shape, dtype=np.uint8)
  v               = np.zeros(default_shape, dtype=np.uint8)
  combined        = np.zeros(default_shape, dtype=np.uint8)
  img             = np.zeros(default_shape, dtype=np.uint8)
  h_title         = "hue"                 
  s_title         = "sat"                 
  v_title         = "val"                 
  combined_title  = "Combined + Morphed" 
  targets_title   = "Targets" 

  #for video capture mode, what approx frame rate do we want? frame rate = approx video_pause + processing time
  video_pause     =  1 #0 milliseconds means wait for key press, waitKey takes an integer so 1 millisecond is minimal with this approach.

  #tuned for the camera settings above and the green leds. (Red didn't work as well and requires changing the threshold function to use OR of inverse and normal threshold, because red is on the top and bottom of the hue scale (wraps around.).)
  hue_delta                   = 15
  sat_delta                   = 25
  val_delta                   = 100
  hue_thresh      = 80
  sat_thresh      = 233
  val_thresh      = 212
  max_thresh      = 255

  #used for the morphologyEx method that fills in the pixels in the combined image prior to identifying polygons and contours.
  kernel     = getStructuringElement(MORPH_RECT, (2,2), anchor=(1,1)) 
  morph_close_iterations = 9

  #colors in BGR format for drawing the targets over the image.
  selected_target_color    = (0,0,255)
  passed_up_target_color   = (255,0,0)
  possible_target_color    = (0,255,0)

  #used to judge whether a polygon side is near vertical or near horizontal, for filtering out shapes that don't match expected target characteristics
  vert_threshold           = math.tan(math.radians(90-20)) 
  horiz_threshold          = math.tan(math.radians(20)) 

  #used to look for only horizontal or vertical rectangles of an aspect ratio that matches the targets.
  #currently open wide to find both horizontal and vertical targets
  max_target_aspect_ratio  = 10 # 1.0 # top target is expected to be 24.5 in x 4 in.
  min_target_aspect_ratio  = 0.1 #0.01# 3# 0.5

  angle_to_robot              = 0 #camera's 0 bearing to robot's 0 bearing
  camera_offset_position      = 0
  morph_close_iterations      = 9
  angle_to_shooter            = 0 #camera's 0 bearing to shooter's 0 bearing
  camera_color_intensity      = 0  #value subject to change
  camera_saturation           = 0  #value subject to change
  camera_contrast             = 0  #value subject to change
  camera_color_hue            = 0  #value subject to change
  camera_brightness           = 20 #value subject to change
  camera_gain                 = 0 #value subject to change
  camera_exposure             = 20
  
  robot_heading               = 0.0 #input from SmartDashboard if enabled, else hard coded here.
  x_resolution                = 640 #needs to match the camera.
  y_resolution                = 480 
  #theta                      = math.radians(49.165) #half of field of view of the camera
#  field_of_view_degrees      = 53.0 horizontal field of view
  field_of_view_degrees       = 26.4382 # vertical field of view
  theta                       = math.radians(field_of_view_degrees/2.0) #half of field of view of the camera, in radians to work with math.tan function.
# real_target_width           = 24.5 #inches #24 * 0.0254 #1 inch / 0.254 meters target is 24 inches wide
  real_target_height          = 28.5 #using these constants and may not be correct for current robot configuration.
  angle_to_shooter            = 0 

  #not currently using these constants and may not be correct for current robot configuration.
  # target_min_width       = 20
  # target_max_width       = 200
  # degrees_horiz_field_of_view = 47.0                                  
  # degrees_vert_field_of_view  = 480.0/640*degrees_horiz_field_of_view 
  # inches_camera_height        = 54.0                                  
  # inches_top_target_height    = 98 + 2 + 98                           
  # degrees_camera_pitch        = 21.0                                  
  # degrees_sighting_offset     = -1.55                                 
  
  def __init__(self, img_path):
    self.img_path = img_path
    self.layout_result_windows(self.h,self.s,self.v)
    self.vc = VideoCapture(0) 
    SmartDashboard.PutNumber(angle_to_robot_title, self.angle_to_robot)
    SmartDashboard.PutNumber(camera_offset_position_title, self.camera_offset_position)
    SmartDashboard.PutNumber(morph_close_iterations_title, self.morph_close_iterations)
    SmartDashboard.PutNumber(angle_to_shooter_title, self.angle_to_shooter)
    SmartDashboard.PutNumber(camera_color_intensity_title, self.camera_color_intensity)
    SmartDashboard.PutNumber(camera_exposure_title, self.camera_exposure)
    SmartDashboard.PutNumber(camera_saturation.title, self.saturation)
    SmartDashboard.PutNumber(camera_contrast_title, self.contrast)
    SmartDashboard.PutNumber(camera_color_hue_title, self.camera_color_hue)
    SmartDashboard.PutNumber(camera_brihtness_title, self.camera_brightness)

  def video_feed(self):
    while True:
      if self.img is not None:
        self.process()

      if self.img_path is None:
        rval, self.img      = self.vc.read() #might set to None
      else:
        self.img            = imread(self.img_path)


  def process(self):
	
    if enable_dashboard:
      self.camera_saturation = int(SmartDashboard.GetNumber(camera_saturation_title) 
      self.angle_to_robot = int(SmartDashboard.GetNumber(angle_to_robot_title)
      self.camera_offset_postion = int(SmartDashboard.GetNumber(camera_offset_position_title)
      self.morph_close_iterations = int(SmartDashboard.GetNumber(morph_close_iterations_title)
      self.angle_to_shooter = int(SmartDashboard.GetNumber(angle_to_shooter_title)
      self.camera_color_intensity = int(SmartDashboard.GetNumber(camera_color_intensity_title)
      self.camera_contrast = int(SmartDashboard.GetNumber(camera_contrast_title)
      self.camera_color_hue = int(SmartDashboard.GetNumber(camera_color_hue_title)
      self.camera_brightness = int(SmartDashboard.GetNumber(camera_brightness_title)
      self.camera_exposure = int(SmartDashboard.GetNumber(camera_exposure_title)
      self.camera_gain = int(SmartDashboard.GetNumber(camera_gain_title)

    if self.img_path is None:
      commands.getoutput(" yavta --set-control '0x009a0901 1' /dev/video0") 
      #print(commands.getoutput(" yavta --get-control '0x009a0901' /dev/video0") )
      commands.getoutput("yavta --set-control '0x009a0902 %s' /dev/video0" % self.camera_exposure) 
      #print(commands.getoutput(" yavta --get-control '0x009a0902' /dev/video0"))


    drawing             = np.zeros(self.img.shape, dtype=np.uint8)


    self.hsv               = cvtColor(self.img, cv.CV_BGR2HSV)
    self.h, self.s, self.v = split(self.hsv)
    self.h_clipped         = self.threshold_in_range(self.h, self.hue_thresh-self.hue_delta, self.hue_thresh+self.hue_delta)
    self.s_clipped         = self.threshold_in_range(self.s, self.sat_thresh-self.sat_delta, self.sat_thresh+self.sat_delta)
    self.v_clipped         = self.threshold_in_range(self.v, self.val_thresh-self.val_delta, self.val_thresh+self.val_delta)
    if show_windows:
      h_scaled = resize(self.h_clipped, window_size)
      s_scaled = resize(self.s_clipped, window_size)
      v_scaled = resize(self.v_clipped, window_size)

      imshow(self.h_title, h_scaled)
      imshow(self.s_title, s_scaled)
      imshow(self.v_title, v_scaled)

    self.find_targets()
   
    if waitKey(self.video_pause) == ord('q'):
      exit(1)

  def layout_result_windows(self, h, s, v):
    if show_windows:
      pos_x, pos_y        = 500,500               
      # imshow(self.img_path, self.img)

      h_scaled        = resize(h, window_size)
      s_scaled        = resize(s, window_size)
      v_scaled        = resize(v, window_size)
      combined_scaled = resize(self.combined, window_size)
      img_scaled      = resize(self.img, window_size)

      imshow(self.h_title       , h_scaled)
      imshow(self.s_title       , s_scaled)
      imshow(self.v_title       , v_scaled)
      imshow(self.combined_title, combined_scaled)
      imshow(self.targets_title , img_scaled)

      #moveWindow(self.h_title, pos_x*1, pos_y*0);
      #moveWindow(self.s_title, pos_x*0, pos_y*1);
      #moveWindow(self.v_title, pos_x*1, pos_y*1);
      #moveWindow(self.combined_title, pos_x*2, pos_y*0);
      #moveWindow(self.targets_title, pos_x*2, pos_y*1);

      #these seem to be placed alphabetically....
      # createTrackbar( "Hue High Threshold:", self.source_title, self.hue_high_thresh, self.max_thresh, self.update_hue_high_threshold);
      # createTrackbar( "Hue Low Threshold:", self.source_title, self.hue_low_thresh, self.max_thresh, self.update_hue_low_threshold);
      # createTrackbar( "Sat High Threshold:", self.source_title, self.sat_high_thresh, self.max_thresh, self.update_sat_high_threshold);
      # createTrackbar( "Sat Low Threshold:", self.source_title, self.sat_low_thresh, self.max_thresh, self.update_sat_low_threshold);
      # createTrackbar( "Val High Threshold:", self.source_title, self.val_high_thresh, self.max_thresh, self.update_val_high_threshold);
      # createTrackbar( "Val Low Threshold:", self.source_title, self.val_low_thresh, self.max_thresh, self.update_val_low_threshold);


  def update_hue_threshold(self, thresh):
    delta = 15
    self.h_clipped = self.threshold_in_range(self.h, thresh-delta, thresh+delta)
    imshow(self.h_title, self.h_clipped)
    self.find_targets()

  def update_sat_threshold(self, thresh):
    delta = 25 
    self.s_clipped = self.threshold_in_range(self.s, thresh-delta, thresh+delta)
    imshow(self.s_title, self.s_clipped)
    self.find_targets()

  def update_val_threshold(self, thresh):
    delta = 100
    self.v_clipped = self.threshold_in_range(self.v, thresh-delta, thresh+delta)
    imshow(self.v_title, self.v_clipped)
    self.find_targets()

  def threshold_in_range(self, img, low, high):
    unused, above = threshold(img, low, self.max_thresh, THRESH_BINARY)
    unused, below = threshold(img, high, self.max_thresh, THRESH_BINARY_INV)
    return bitwise_and(above, below)

  def find_targets(self):
    #combine all the masks together to get their overlapping regions.
    if True: 
      self.reset_targeting()
      self.combined = bitwise_and(self.h_clipped, bitwise_and(self.s_clipped, self.v_clipped))

      #comment above line and uncomment next line to ignore hue channel til we sort out red light hue matching around zero.  
      #self.combined = bitwise_and(self.s_clipped, self.v_clipped)
      
      self.combined = morphologyEx(src=self.combined, op=MORPH_CLOSE, kernel=self.kernel, iterations=self.morph_close_iterations)   
      if show_windows:
        combined_scaled = resize(self.combined, window_size)
        imshow(self.combined_title, combined_scaled )

      self.contoured      = self.combined.copy() 
      contours, heirarchy = findContours(self.contoured, RETR_LIST, CHAIN_APPROX_TC89_KCOS)
      #print("number of contours found = "+str(len(contours)))
      
      #contours = [convexHull(c.astype(np.float32),clockwise=True,returnPoints=True) for c in contours]
      # 
      polygon_tuples = self.contours_to_polygon_tuples(contours)        
      polygons       = [self.unpack_polygon(t) for t in polygon_tuples] 


      for polygon_tuple in polygon_tuples:
        self.mark_correct_shape_and_orientation(polygon_tuple) 

      if self.selected_target is not None:
        self.draw_target(self.lowest_found_so_far_x, self.lowest_found_so_far, self.selected_target_color)
        drawContours(self.drawing, contours, -1, self.selected_target_color, thickness=10)
#        drawContours(self.drawing, [self.unpack_polygon(self.selected_target).astype(np.int32)], -1, self.selected_target_color, thickness=10)
        self.aim()

      if show_windows:
        drawing_scaled = resize(self.drawing, window_size)
        imshow(self.targets_title, drawing_scaled)

      if enable_dashboard:
        SmartDashboard.PutNumber("Potential Targets:", len(polygons))
        print("Potential Targets:", len(polygons))

  def aim(self):
    if enable_dashboard:
      self.robot_heading    = SmartDashboard.GetNumber(robot_heading_title)

    polygon, x, y, w, h   = self.selected_target
    self.target_bearing   = self.get_bearing(x + w/2.0)   
    self.target_range     = self.get_range(x, y, w, h)     
    #self.target_elevation = self.get_elevation(x, y, w, h) 
    print("Range = " + str(self.target_range))
    print("Bearing = " + str(self.target_bearing))
    if enable_dashboard:
      SmartDashboard.PutNumber("Target Range:",    self.target_range)
      SmartDashboard.PutNumber("Target Bearing:",  self.target_bearing)
      SmartDashboard.PutNumber("Target Elevation:",self.target_elevation)
      SmartDashboard.PutString("Target: ","Acquired!")


  def get_bearing(self, target_center_x):
    return (self.field_of_view_degrees/self.x_resolution)*(target_center_x-(self.x_resolution/2))-self.angle_to_shooter

  def get_range(self, x, y, w, h):
    if enable_dashboard:
      SmartDashboard.PutNumber("TargetWidth: ",w)
      SmartDashboard.PutNumber("TargetHeight",h)
      SmartDashboard.PutNumber("TargetX",x)
      SmartDashboard.PutNumber("TargetY",y)

    return self.distance(h)

  def distance(self, pix_height):
    fovr = self.x_resolution * self.real_target_height / pix_height
    if enable_dashboard:
      SmartDashboard.PutNumber("FieldOfViewReal", fovr) # = 2w_real
      SmartDashboard.PutNumber("TanTheta", math.tan(self.theta))
      SmartDashboard.PutNumber("fovr/tan(theta)", fovr/math.tan(self.theta))

    return self.real_target_height*self.y_resolution/(2*pix_height*math.tan(self.theta))

  def reset_targeting(self):
    if enable_dashboard:
      SmartDashboard.PutString("Target: ","lost...")
      
    self.drawing                = self.img.copy() 
    self.selected_target        = None            
    self.lowest_found_so_far_x  = None            
    self.lowest_found_so_far    = 0      
    self.target_range           = 0               
    self.target_bearing         = -1               
    self.target_elevation       = 0               

  def mark_correct_shape_and_orientation(self, polygon_tuple):
    p,x,y,w,h                               = polygon_tuple
    if True: #isContourConvex(p) and 4==len(p) and self.slope_angles_correct(p):
      center_x = int(x + w/2.0)
      center_y = int(y + h/2.0)
      self.draw_target(center_x, center_y, self.possible_target_color)

      if center_y > self.lowest_found_so_far:
        self.selected_target = polygon_tuple
        self.lowest_found_so_far   = center_y
        self.lowest_found_so_far_x = center_x

    else:
      drawContours(self.drawing, [p.astype(np.int32)], -1, self.passed_up_target_color, thickness=7)

  def draw_target(self, center_x, center_y, a_color):
    #circle(self.drawing,(center_x, center_y), radius=10, color=self.selected_target_color, thickness=5)
    radius      = 10 
    a_thickness = 5  
    line(self.drawing, (center_x - radius, center_y), (center_x + radius, center_y), color=a_color, thickness=a_thickness)
    line(self.drawing, (center_x, center_y-radius), (center_x, center_y+radius), color=a_color, thickness=a_thickness)

  def slope_angles_correct(self, polygon):
    num_near_vert, num_near_horiz = 0,0
    for line_starting_point_index in xrange(0,4):
      slope = self.get_slope(polygon, line_starting_point_index)
      if slope < self.horiz_threshold:
        num_near_horiz += 1 
      if slope > self.vert_threshold:
        num_near_vert += 1 

    return 1 <= num_near_horiz and 2 == num_near_vert

  def get_slope(self, p, line_starting_point_index):
    line_ending_point_index = (line_starting_point_index+1)%4
    dy = p[line_starting_point_index, 0, 1] - p[line_ending_point_index, 0, 1]
    dx = p[line_starting_point_index, 0, 0] - p[line_ending_point_index, 0, 0]
    slope = sys.float_info.max
    if 0 != dx:
      slope = abs(float(dy)/dx)

    return slope

  def unpack_polygon(self,t):
    p,x,y,w,h = t
    return p

  def contours_to_polygon_tuples(self, contours):
    polygon_tuples = []
    for c in contours:
      x, y, w, h = boundingRect(c)
      if self.aspect_ratio_and_size_correct(w,h):
        p = approxPolyDP(c, 20, False)
        polygon_tuples.append((p,x,y,w,h))


    return polygon_tuples 

  def aspect_ratio_and_size_correct(self, width, height):
    ratio = float(width)/height #float(height)/width
    return ratio < self.max_target_aspect_ratio and ratio > self.min_target_aspect_ratio #and width > self.target_min_width and width < self.target_max_width
    #note: we don't want to ignore potential targets based on pixel width and height since range will change the pixel coverage of a real target.

 
if '__main__'==__name__:
  try:
    img_path = sys.argv[1]
  except:
    img_path= None
    # print('Please add an image path argument and try again.')
    # sys.exit(2)

  ImageProcessor(img_path).video_feed()
