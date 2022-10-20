import time
import sys
import numpy as np
import re
from .UniformChecker import UniformChecker
from OZEngine.dress_classifier import classification2
from OZEngine.lib.utils import sortContoursByArea, getVertexCnt, getContourCenterPosition, getRectCenterPosition, isPointInBox
from OZEngine.lib.defines import *
from OZEngine.lib.ocr import OCR
from OZEngine.lib.utils import plt_imshow

# (동)정복 검사


class FullDressUniformChecker(UniformChecker):
    def __init__(self, train_mode):
        # hyperparameter
        filter = {
            'name_tag': {
                'lower': (25, 0, 210), 
                'upper': (255, 15, 255)
            },
            'uniform': {
                'lower': (0, 0, 0),
                'upper': (255, 255, 50)
            },
            'class_tag': {
                'lower': (140, 60, 60),
                'upper': (190, 255, 255)
            },
            'anchor': {
                'lower': (20, 100, 100),
                'upper': (30, 255, 255)
            },
            'mahura': {
                'lower': (140, 120, 50), 
                'upper': (190, 255, 255)
            }
        }
        super().__init__(filter, 'full_dress_uniform', train_mode)
        self.name_cache = None
        self.debug_cnt = 0

        self.W = 0

    def getPosition(self, contour):
        center_p = getContourCenterPosition(contour)
        position = 'left' if center_p[0] < (self.W//2) else 'right'
        return position
    

    def isNameTag(self, contour, position, kind):
        return position == 'left' and kind == 'name_tag' and cv2.contourArea(contour) > 100

    def isClassTag(self, contour, position, kind):
        return position == 'left' and kind is not None and kind.find('class_tag') != -1 and cv2.contourArea(contour) > 100

    def isAnchor(self, contour, position, kind):
        return kind == 'anchor' and cv2.contourArea(contour) > 100

    def isMahura(self, kind):
        return kind == 'mahura'

    def isInShirt(self, contour):
        # 샘브레이 영영 안쪽 && 모서리가 4~5 && 크기가 {hyperParameter} 이상 => (이름표 or 계급장)
        return 3 <= getVertexCnt(contour) <= 10 and cv2.contourArea(contour) > 300

    def checkUniform(self, org_img):
        img = org_img
        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        H, W = img.shape[: 2]
        self.W = W

        box_position_dic = {}
        component_dic = {}
        masked_img_dic = {}
        probability_dic = {}

        # 이름표, 마후라 체크
        name = 'name_tag'
        contours, _,  masked_img_dic[name] = self.getMaskedContours(
            img=img, hsv_img=hsv_img, kind='name_tag', sort=True)

        if contours is not None:
            for contour in contours:
                is_name_tag = component_dic.get('name_tag')
                is_mahura = component_dic.get('mahura')
                area = cv2.contourArea(contour)

                if is_name_tag and is_mahura or (area < 1000):
                    break

                position = self.getPosition(contour)

                tmp_box_position = cv2.boundingRect(contour)
                x,y,w,h = tmp_box_position
                parts_img = img[y:y+h, x:x+w]

                isCenter = x < W < x+w

                if self.train_mode:
                    probability, kind = 0, name
                else:
                    probability, kind = self.parts_classifier.predict(parts_img)[:2]

                if not is_name_tag and self.isNameTag(contour, position, kind):
                    # 이름표 OCR
                    if self.name_cache:
                        box_position = tmp_box_position
                        component = self.name_cache
                    else:
                        ocr_list = OCR(img)
                        self.debug_cnt += 1
                        box_position, component = self.getName(contour, ocr_list)
                        self.name_cache = component

                    box_position_dic['name_tag'] = box_position
                    component_dic['name_tag'] = component
                    probability_dic['name_tag'] = probability
                
                elif not is_mahura and isCenter and self.isMahura(kind):
                    box_position_dic['mahura'] = tmp_box_position
                    component_dic['mahura'] = True
                    probability_dic['mahura'] = probabilit

        # 네카치프 / 네카치프링 체크
        name = 'anchor'
        contours, masked_img_dic[name] = self.getMaskedContours(
            img=img, hsv_img=hsv_img, kind=name)
        
        if contours is not None:
            for contour in contours:
                area = cv2.contourArea(contour)

                if area < 100:
                    break

                position = self.getPosition(contour)
                tmp_box_position = cv2.boundingRect(contour)
                x,y,w,h = tmp_box_position
                parts_img = img[y:y+h, x:x+w]

                if self.train_mode:
                    kind = name
                else:
                    probability, kind = self.parts_classifier.predict(parts_img)[:2]
                if self.isAnchor(contour, position, kind):
                    box_position_dic[name] = tmp_box_position
                    component_dic[name] = True
                    probability_dic[name] = probability
                    break

        # 계급장 체크
        name = 'class_tag'
        contours, _, masked_img_dic[name] = self.getMaskedContours(
            img=img, hsv_img=hsv_img, kind=name, sort=True)
            
        if contours is not None:
            for contour in contours:
                area = cv2.contourArea(contour)

                if area < 100:
                    break
                position = self.getPosition(contour)

                tmp_box_position = cv2.boundingRect(contour)
                x,y,w,h = tmp_box_position
                parts_img = img[y:y+h, x:x+w]

                if self.train_mode:
                    kind = name
                else:
                    probability, kind = self.parts_classifier.predict(parts_img)[:2]
                if self.isClassTag(contour, position, kind):
                    box_position_dic[name] = tmp_box_position
                    class_n = kind.split('+')[1]
                    component_dic[name] = Classes.dic.get(int(class_n))
                    probability_dic[name] = probability
                    break

        return {'component':component_dic, 'box_position':box_position_dic, 'masked_img':masked_img_dic, 'probability':probability_dic}
