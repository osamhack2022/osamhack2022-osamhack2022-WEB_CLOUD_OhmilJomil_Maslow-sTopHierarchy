import cv2
from datetime import datetime



from app.models.inspection_log import InspectionLog
from app.models.inspection_detail import InspectionDetail
from app.core.config import settings

from app.api.websocket.image import img_2_photo
from app.api.simple.image_box import ImageBox


MAIN_IMAGE_PATH = f"{settings.IMAGE_PATH}/inspection"

EXPIRATION_COUNT = 5
class BaseWorker:
    """
    이미지 경로를 받음
    받은 경로의 이미지를 가져옴
    가져온 이미지를 ai에게 넘겨줌
    ai 가 정보를 갱신
    ㄴ 새로운 정보면 DB에 create
    ㄴ 업데이트가 필요하면 DB에 update
    ㄴ 둘다 아닌 경우 무시

    """
    def __init__(self, db, ai, guardhouse):
        self.db = db
        self.image_box = ImageBox(ai=ai, guardhouse=guardhouse)
        self.db_data_id = None
        self.parts_path = {}
        # 파일 경로 지정
        name = datetime.now().strftime("%H-%M-%S")
        self.main_image_path = f"{MAIN_IMAGE_PATH}/{guardhouse}_{name}.jpg"
        # REFRESH_COUNT
        self.expiration_count = EXPIRATION_COUNT

    def create_data(self):
        # 생성할 정보 가져오기
        data_dict = self.image_box.get_inspection()
        # model 객체 생성
        print(f"DB 데이터 생성 - {data_dict}")
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
        part_list = self.image_box.get_parts()
        for part_name, status in part_list.items():
            db_part = InspectionDetail(
                inspection_id=self.db_data_id,
                appearance_type=PART_ID[part_name],
                status=status,
                image_path="",
            )
            self.db.add(db_part)
            self.db.commit()
            self.db.refresh(db_part)

        self.expiration_count = EXPIRATION_COUNT
        print("DB에 데이터 생성 완료")


    def update_data(self):
        db_data = self.db.query(InspectionLog).filter_by(inspection_id=self.db_data_id)
        if not db_data.count():
            raise NotImplementedError(f"해당 객체를 조회할 수 없음 - {self.db_data_id}")

        inspection_dict = self.image_box.get_inspection()
        db_data.update(inspection_dict)
        self.db.commit()

        self.expiration_count = EXPIRATION_COUNT
        print(f"업데이트 완료")
       
            
    
    def update_parts(self, part_name):
        db_data = self.db.query(InspectionDetail).filter_by(inspection_id=self.db_data_id).filter_by(appearance_type=PART_ID[part_name])
        if not db_data.count():
            raise NotImplementedError(f"해당 객체를 조회할 수 없음 - {self.db_data_id}")

        part_dict = {
            "status": True,
            "image_path": self.parts_path[part_name]
        }
        
        db_data.update(part_dict)
        self.db.commit()

        self.expiration_count = EXPIRATION_COUNT
        print(f"파츠 업데이트 완료 - {part_name}")



class SimpleWorker(BaseWorker):
     def execute(self, img):

        # ai에게 처리
        # print("이미지 처리 시작 ===============================")
        result = self.image_box.image_process(image=img)
        self.expiration_count -= 1 #인식 횟수 감소
        # 군복이 아닌 경우
        if not result:
            return {
                "msg" : "no mailtary"
            }

        # 답장
        photo  = img_2_photo(result['boxed_img'])

        # 메세지 제작
        msg =  {
            "type": "result",
            "photo": photo,
        }
        msg.update(inspection_dict)
        msg.update(parts_dict)
        return msg

 