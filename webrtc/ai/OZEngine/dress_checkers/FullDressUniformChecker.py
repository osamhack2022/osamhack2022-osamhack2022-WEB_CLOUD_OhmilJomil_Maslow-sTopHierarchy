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
            'uniform': {
                'lower': (0, 0, 0),
                'upper': (255, 255, 50)
            },
            'class_tag': {
                'lower': (140, 120, 50),
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
        self.name_tag_pattern = re.compile('[가-힣]+')
 
    

    def isNameTag(self, contour, position, kind):
        return position == 'left' and kind == 'name_tag' and cv2.contourArea(contour) > 100

    def isClassTag(self, contour, position, kind):
        return position == 'left' and kind == 'class_tag'

    def isAnchor(self, contour, position, kind):
        return kind == 'anchor' and cv2.contourArea(contour) > 100

    def isMahura(self, contour, position, kind):
        return kind == 'mahura'

    def isInShirt(self, contour):
        # 샘브레이 영영 안쪽 && 모서리가 4~5 && 크기가 {hyperParameter} 이상 => (이름표 or 계급장)
        return 3 <= getVertexCnt(contour) <= 10 and cv2.contourArea(contour) > 300

    def checkUniform(self, org_img):
        img = org_img
        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        H, W = img.shape[: 2]

        box_position_dic = {}
        component_dic = {}
        masked_img_dic = {}

        # 이름표 체크
        name = 'name'
        contours, sorted_hierarchy, masked_img_dic['shirt'] = self.getMaskedContours(
            img=img, hsv_img=hsv_img, kind='uniform', sort=True)
            
        for i, (contour, lev) in enumerate(zip(contours, sorted_hierarchy)):
            if i == 0:  # 옷
                cur_node, next_node, prev_node, first_child, parent = lev
                shirt_node = cur_node
                continue

            if parent == shirt_node and self.isInShirt(contour):
                box_position = cv2.boundingRect(contour)
                center_p = getContourCenterPosition(contour)

                x,y,w,h = cv2.boundingRect(contour)
                parts_img = img[y:y+h, x:x+w]

                if self.train_mode:
                    kind = name
                else:
                    kind = self.parts_classifier.predict(parts_img)[1]

                position = 'left' if center_p[0] < (W//2) else 'right'
                if not is_name_tag and self.isNameTag(contour, position, kind):
                    # 이름표 OCR
                    if self.name_cache:
                        box_position = cv2.boundingRect(contour)
                        component = 'cached ' + self.name_cache
                    else:
                        ocr_list = OCR(img)
                        self.debug_cnt += 1
                        box_position, component = self.getName(contour, ocr_list)
                        self.name_cache = component

                    # return값에 반영
                    box_position_dic[name] = box_position
                    component_dic[name] = component
                    break

        # 네카치프 / 네카치프링 체크
        name = 'anchor'
        contours, masked_img_dic[name] = self.getMaskedContours(
            img=img, hsv_img=hsv_img, kind=name)
        
        for contour in contours:
            center_p = getContourCenterPosition(contour)
            position = 'left' if center_p[0] < (W//2) else 'right'

            x,y,w,h = cv2.boundingRect(contour)
            parts_img = img[y:y+h, x:x+w]

            if self.train_mode:
                kind = name
            else:
                kind = self.parts_classifier.predict(parts_img)[1]
            if self.isAnchor(contour, position, kind):
                box_position_dic[name] = cv2.boundingRect(contour)
                component_dic[name] = True
                break

        # 계급장 체크
        name = 'class_tag'
        contours, masked_img_dic[name] = self.getMaskedContours(
            img=img, hsv_img=hsv_img, kind=name)

        for contour in contours:
            center_p = getContourCenterPosition(contour)
            position = 'left' if center_p[0] < (W//2) else 'right'

            x,y,w,h = cv2.boundingRect(contour)
            parts_img = img[y:y+h, x:x+w]

            if self.train_mode:
                kind = name
            else:
                kind = self.parts_classifier.predict(parts_img)[1]
            if self.isNameTag(contour, position, kind):
                box_position_dic[name] = cv2.boundingRect(contour)
                component_dic[name] = True
                break

        # 마후라 체크
        # name = 'mahura'
        # contours = self.getMaskedContours(
        #     img=img, hsv_img=hsv_img, kind=name, sort=False)
        # box_position_dic[name], component_dic[name] = self.getMahura(
        #     img, contours, None)

        return component_dic, box_position_dic, masked_img_dic
