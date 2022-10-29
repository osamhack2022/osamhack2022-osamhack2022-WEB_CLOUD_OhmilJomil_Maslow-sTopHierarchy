import cv2
from datetime import datetime

from app.core.config import settings

from app.api.worker.ai import AIWorker
from app.api.image_box.db_adapter import ai_2_db_main, get_part_id

from app.api.db.guardhouse import select_guardhouse
from app.crud.unit_house_relation import get_unit_from_house

from app.models.inspection_log import InspectionLog
from app.models.inspection_detail import InspectionDetail

MAIN_IMAGE_PATH = f"{settings.IMAGE_PATH}/inspection"
PARTS_IMAGE_PATH = f"{settings.IMAGE_PATH}/detail"



class FileWorker(AIWorker):
    def __init__(self, guardhouse):
        super().__init__()
        name = datetime.now().strftime("%H-%M-%S")
        self.file_name = f"{guardhouse}_{name}"
        self.main_image_path = f"{MAIN_IMAGE_PATH}/{self.file_name}.jpg"
        self.part_image_path = {}

    def save_main_img(self):
        img = self.image_box.main_image
        cv2.imwrite(self.main_image_path, img)

    def save_part_img(self, part_name):
        img = self.image_box.parts_images[part_name]
        self.part_image_path[part_name] = f"{PARTS_IMAGE_PATH}/{self.file_name}_{part_name}.jpg"
        cv2.imwrite(self.part_image_path[part_name], img)
        return self.part_image_path[part_name]



class DBWorker(FileWorker):

    def __init__(self, guardhouse, db):
        super().__init__(guardhouse)
        self.db = db
        self.db_data_id = None
    
   
    def create_main(self, work_time):
        # 이미지 저장
        self.save_main_img()

        # 생성할 정보 가져오기
        data_dict = self.image_box.inspection
        data_dict = ai_2_db_main(data_dict)
        data_dict['guardhouse'] = select_guardhouse(self.db, data_dict['guardhouse'])
        
        # 부대 알고리즘
        data_dict['military_unit'] = get_unit_from_house(
            db=self.db,
            house=data_dict['guardhouse'],    # 해당 항목은 webrtc에서 입력시 DB에 존재하는 값만 입력가능
            access_time=work_time, 
            affiliation= data_dict['affiliation'] if data_dict['affiliation'] == 1 else None, 
            rank=data_dict['rank'] if data_dict['rank'] == 1 else None, 
            name=data_dict['name'] if data_dict['name'] == 1 else None, 
        )         

        # DB에 저장
        db_data = InspectionLog(
            guardhouse=data_dict['guardhouse'],
            affiliation=data_dict['affiliation'],
            rank=data_dict['rank'],
            name=data_dict['name'],
            uniform=data_dict['uniform'],
            image_path=self.main_image_path,
        )
        self.db.add(db_data)
        self.db.commit()
        self.db.refresh(db_data)
        # pk 값은 worker에서 보관
        self.db_data_id = db_data.inspection_id  


        # 각 파츠도 DB에 생성
        part_list = self.image_box.parts
        for part_name, status in part_list.items():
            if self.image_box.parts_images.get(part_name) is not None:
                path = self.save_part_img(part_name)
            else:
                path = ""

            db_part = InspectionDetail(
                inspection_id=self.db_data_id,
                appearance_type=get_part_id(part_name),
                status=status,
                image_path="",
            )
            self.db.add(db_part)
            self.db.commit()
            self.db.refresh(db_part)
        print("DB에 데이터 생성 완료")



    def update_main(self):
        pass


    def update_parts(self):
        pass
    