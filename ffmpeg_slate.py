from PySide6.QtWidgets import *
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile
from PySide6.QtGui import QPixmap, QFont
from functools import partial
import sys
import os
import time
import re
import glob
import cv2
import subprocess
import threading


class EncoderTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setting()
        self.slate_list = ["None","Shot Number","Project","Date Created","Task","Version","Time/Frame"]
        self.location = ["top_left","top_center","top_right","bot_left","bot_center","bot_right"]
        
        self.ui.pushButton_open_file.clicked.connect(self.open_file)
        for i in self.location:
            getattr(self.ui,f"comboBox_{i}").currentIndexChanged.connect(partial(self._set_slate_text,i))
        self.ui.comboBox_font_style.currentIndexChanged.connect(self._set_font_style)
        self.ui.pushButton_render.clicked.connect(self._make_total_cmd)
    
    def _make_drawtext(self):    # ffmpeg로 영상에 들어갈 글씨 및 삽입 위치 정하기
        selected_font_size = self._make_font_size()
        selected_font = self.ui.comboBox_font_style.currentText()
        font_path = f"/usr/share/fonts/Courier_Prime/{selected_font}.ttf"
        drawtext_list = []
        for i in self.location:
            if i == "top_left":
                x = "10"
                y = "10"
            elif i == "top_center":
                x = "(w-tw)/2"
                y = "10"
            elif i == "top_right":
                x = "w-tw-10"
                y = "10"
            elif i == "bot_left":
                x = "10"
                y = "h-th-10"
            elif i == "bot_center":
                x = "(w-tw)/2"
                y = "h-th-10"
            elif i == "bot_right":
                x = "w-tw-10"
                y = "h-th-10"
            
            if getattr(self.ui,f"comboBox_{i}").currentText() == "None":
                text = ""
            elif getattr(self.ui,f"comboBox_{i}").currentText() == "Shot Number":
                text = self.info_dict["shot number"]
            elif getattr(self.ui,f"comboBox_{i}").currentText() == "Project":
                text = self.info_dict["project"]
            elif getattr(self.ui,f"comboBox_{i}").currentText() == "Date Created":
                text = self.info_dict["date created"]
            elif getattr(self.ui,f"comboBox_{i}").currentText() == "Task":
                text = self.info_dict["task"]
            elif getattr(self.ui,f"comboBox_{i}").currentText() == "Version":
                text = self.info_dict["version"]
            elif getattr(self.ui,f"comboBox_{i}").currentText() == "Time/Frame":
                text = "%{n}"+f"\/{self.first_frame}-{self.last_frame}" + ":start_number = 1001"
            
            drawtext = ""
            drawtext += " ".join([
                f"drawtext=fontfile={font_path}:"
                f"text='{text}':"   
                f"x={x}:"
                f"y={y}:"
                f"fontcolor=white@0.7:"
                f"fontsize={selected_font_size}"
            ])
            drawtext_list.append(drawtext)
            
        self.drawtexts = ""
        self.drawtexts += ", ".join(drawtext_list)
    
    def _make_codec(self):  # 변환할 코덱 정하기
        if self.ui.comboBox_codec.currentText() == "H.264":
            return "libx264"
        elif self.ui.comboBox_codec.currentText() == "ProRes":
            return "prores_ks"
    
    def _make_ext(self):    # 변환할 확장자 정하기
        if self.ui.comboBox_ext.currentText() == "mp4":
            return "mp4"
        elif self.ui.comboBox_ext.currentText() == "mov":
            return "mov"
        
    def _make_font_size(self):  # 슬레이트 폰트 사이즈 정하기 ..ing
        result = self.ui.spinBox_font_size.value()
        return result
        
    def render_slate(self,cmd): # 프로그레스 바 작동시키기, 영상 렌더하기
        result = subprocess.Popen([cmd], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.STDOUT,
                               universal_newlines=True,
                               shell=True
                               )
        for line in result.stdout:
            if line.startswith("frame="):
                p = re.compile("[f][r][a][m][e][=][ ]*\d*")
                p_data = p.search(line)
                frame_source = p_data.group()
                frame = frame_source.split("frame=")[-1].strip()
                print(frame)
                last = int(self.info_dict["last frame"])-int(self.info_dict["first frame"])+1
                p_value = int(frame)/last*100
                self.ui.progressBar.setValue(p_value)
            else:
                pass
    
    def _check_slate_num(self): # 중복된 슬레이트 파일 이름 피하기
        orig_name = self.file_path.split(".")[0]
        selected_ext = self._make_ext()
        cmd_output = f"{orig_name}_slate.{selected_ext}"
        if not os.path.exists(cmd_output):
            return cmd_output
        files = glob.glob(f"{orig_name}_slate_*.{selected_ext}")
        if not files:
            cmd_output = f"{orig_name}_slate_1.{selected_ext}"
        else:
            files.sort()
            last_path = files[-1]
            p = re.compile("[_][s][l][a][t][e][_]\d*")
            p_data = p.search(last_path)
            last_slate = p_data.group()
            last_num = int(last_slate.split("_")[-1])
            cmd_output = f"{orig_name}_slate_{last_num+1}.{selected_ext}"
        return cmd_output
    
    def _make_total_cmd(self): # ffmpeg str 취합
        self._make_drawtext()
        orig_name = self.file_path.split(".")[0]
        
        if self.ext == "mov":
            cmd_input = f"ffmpeg -i {self.file_path} "
        elif self.ext in ["exr", "jpg", "png"]:
            cmd_input = ""
            cmd_input += " ".join([
                "ffmpeg",
                f"-start_number 1001",
                f"-framerate 24", 
                f"-i {orig_name}.%04d.{self.ext}"
            ])
        selected_codec = self._make_codec()
        codec = f"-c:v {selected_codec}"
        drawbox_top = "drawbox=x=0:y=0:w=iw:h=ih*0.07:color=black:t=fill"
        drawbox_bot = "drawbox=x=0:y=ih*0.93:w=iw:h=ih*0.07:color=black:t=fill"
        cmd_output = self._check_slate_num()
        
        cmd = f'''{cmd_input} {codec} -vf "{drawbox_top}, {drawbox_bot}, {self.drawtexts}" {cmd_output} -y'''
        t = threading.Thread(target=partial(self.render_slate,cmd))
        t.start()
        
    def open_file(self):    # 변경할 영상 소스 삽입, 삽입 후 UI채우기
        self.file_tuple = QFileDialog.getOpenFileName(self, "import source file", "/home/rapa/show")
        self._take_file_info()
        self._make_thumbnail()
        self._set_info_data()
        self._set_slate_viewer()
        self._set_slate_style()
        
    def _set_slate_style(self): # 슬레이트 스타일 바꾸기 ..ing
        self.ui.spinBox_font_size.setValue(60)
        self.ui.comboBox_font_style.addItems(["CourierPrime-Bold","CourierPrime-BoldItalic","CourierPrime-Italic","CourierPrime-Regular"])
        
    def _set_font_style(self):  # 폰트 스타일 slate viewer에 미리보기 띄우기
        font = QFont()
        font.setFamilies([u"Courier Prime"])
        if self.ui.comboBox_font_style.currentText() in ["CourierPrime-Bold","CourierPrime-BoldItalic"]:
            font.setBold(True)
        else:
            font.setBold(False)
            
        font.setPointSize(10)
        
        if self.ui.comboBox_font_style.currentText() in ["CourierPrime-BoldItalic","CourierPrime-Italic"]:
            font.setItalic(True)
        else:
            font.setItalic(False)
            
        for location in self.location:
            getattr(self.ui,f"label_{location}").setFont(font)
        
    def _set_slate_text(self,location,idx): # 미리보기 텍스트 삽입
        if idx == 0:
            getattr(self.ui,f"label_{location}").setText("")
        elif idx == 1:
            getattr(self.ui,f"label_{location}").setText(self.info_dict["shot number"])
        elif idx == 2:
            getattr(self.ui,f"label_{location}").setText(self.info_dict["project"])
        elif idx == 3:
            getattr(self.ui,f"label_{location}").setText(self.info_dict["date created"])
        elif idx == 4:
            getattr(self.ui,f"label_{location}").setText(self.info_dict["task"])
        elif idx == 5:
            getattr(self.ui,f"label_{location}").setText(self.info_dict["version"])
        elif idx == 6:
            # now_time = "TC 00:00:00"
            getattr(self.ui,f"label_{location}").setText(f"1001/{self.frame_show}")
            
    def _set_slate_viewer(self):  # UI 콤보박스 리스트 삽입/초기 셋팅
        # 슬레이트에 삽입될 텍스트 위치 및 내용
        index = 1
        for i in self.location:
            getattr(self.ui,f"comboBox_{i}").addItems(self.slate_list)
            getattr(self.ui,f"comboBox_{i}").setCurrentIndex(index)
            index += 1
        
        # 썸네일 이미지 삽입
        th_path = f"/home/rapa/.thumbnail/{self.file_name}_thumbnail.jpg"
        p = QPixmap(th_path)
        s_p = p.scaledToWidth(640)
        self.ui.label_th.setPixmap(s_p)
        
        # 변환할 코덱 설정
        self.ui.comboBox_codec.addItems(["H.264","ProRes"])
        self.ui.comboBox_codec.setCurrentIndex(1)
        
        # 변환할 확장자 설정
        self.ui.comboBox_ext.addItems(["mp4", "mov"])
        self.ui.comboBox_ext.setCurrentIndex(1)
               
    def _set_info_data(self):   # 삽입한 영상 소스 정보 보여주기
        self.ui.label_file.setText(self.info_dict["file name"])
        self.ui.label_project.setText(self.info_dict["project"])
        self.ui.label_shot_num.setText(self.info_dict["shot number"])
        self.ui.label_task.setText(self.info_dict["task"])
        self.ui.label_ver.setText(self.info_dict["version"])
        self.ui.label_date.setText(self.info_dict["date created"])
        first = self.info_dict["first frame"]
        last = self.info_dict["last frame"]
        self.frame_show = f"{first} - {last}"
        self.ui.label_frame_range.setText(self.frame_show)
        w = self.info_dict["width"]
        h = self.info_dict["height"]
        frame_size = f"{w} x {h}"
        self.ui.label_frame_size.setText(frame_size)
        
    def _make_thumbnail(self):  # 썸네일 만들기
        if not os.path.exists("/home/rapa/.thumbnail"):
            os.mkdir("/home/rapa/.thumbnail")
        if self.ext == "mov":
            # cmd = f"ffmpeg -i {self.file_path} -an -ss 00:00:03 -an -r 2 -vframes 1 -y /home/rapa/.thumbnail/{self.file_name}_thumbnail.jpg -y"
            cmd = f"ffmpeg -ss 00:00:00 -i {self.file_path} -frames:v 3 /home/rapa/.thumbnail/{self.file_name}_thumbnail.jpg -y"
            print(cmd)
            os.system(cmd)
        elif self.ext in ["exr", "jpg", "png"]:
            file_dir = os.path.dirname(self.file_path)
            ext_files = glob.glob(f"{file_dir}/{self.sp_dot_name[0]}.*.{self.ext}")
            thumb_path = ext_files[3]
            cmd = f"ffmpeg -i {thumb_path} /home/rapa/.thumbnail/{self.file_name}_thumbnail.jpg -y"
            os.system(cmd)
            
    def _take_file_info(self):  # 삽입한 영상 소스 정보 취합
        self.file_path = self.file_tuple[0]   #
        print(self.file_path)
        self.file_name = self.file_path.split("/")[-1]    #
        
        p = re.compile("show/*[.a-zA-Z0-9]+")
        p_data = p.search(self.file_path)
        if p_data:
            show_project = p_data.group()
        project = show_project.split("/")[1]    #
        
        split_name = self.file_name.split("_")
        shot_num = f"{split_name[0]}_{split_name[1]}"   #
        task = self.file_name.split("_")[2]  #
        
        
        self.sp_dot_name = self.file_name.split(".")
        self.ext = self.sp_dot_name[-1]
        if self.ext == "mov":
            # 동영상의 전체 프레임 수 확인
            video = cv2.VideoCapture(f"{self.file_path}")
            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT)) 
            self.first_frame = "1"   
            self.last_frame = str(total_frames)        
            # 동영상의 프레임 크기 확인
            width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        elif self.ext in ["exr", "jpg", "png"]:
            # 동영상의 전체 프레임 수 확인
            frame_list = []
            file_dir = os.path.dirname(self.file_path)
            ext_files = glob.glob(f"{file_dir}/{self.sp_dot_name[0]}.*.{self.ext}")
            for file in ext_files:
                p = re.compile(f".....{self.ext}")
                p_data = p.search(file)
                if p_data:
                    frame_num = p_data.group()
                    frame_list.append(frame_num)
            frame_list.sort()
            self.first_frame = frame_list[0].split(".")[0]   #
            self.last_frame = frame_list[-1].split(".")[0]   #
            # 동영상의 프레임 크기 확인
            cmd = f"ffprobe -v error -show_streams {self.file_path}"
            result = subprocess.run([cmd],shell=True,stdout=subprocess.PIPE,text=True)
            list = result.stdout.split("\n")
            for line in list:
                if line.startswith("width="):
                    width = line.split("=")[1]
                elif line.startswith("height="):
                    height = line.split("=")[1]
            # img = cv2.imread(self.file_path)
            # height, width, channel = img.shape
        
        p = re.compile("[v]\d{3}")
        p_data = p.search(self.file_path)
        if p_data:
            ver = p_data.group()    #
        
        # 파일 수정 날짜 가져오기
        # file_stat = os.stat(file_path)
        # modified_timestamp = file_stat.st_mtime
        # modified_date = time.strftime('%Y-%m-%d', time.localtime(modified_timestamp)
        
        now = time
        created_date = now.strftime('%Y-%m-%d') #
        
        self.info_dict = {}
        self.info_dict["file path"] = self.file_path
        self.info_dict["file name"] = self.file_name
        self.info_dict["project"] = project
        self.info_dict["shot number"] = shot_num
        self.info_dict["task"] = task
        self.info_dict["version"] = ver
        self.info_dict["first frame"] = self.first_frame
        self.info_dict["last frame"] = self.last_frame
        self.info_dict["width"] = width
        self.info_dict["height"] = height
        self.info_dict["date created"] = created_date
        
    def setting(self):  # UI초기 셋팅
        self.root_path = sys.path[0]
        ui_file_path = f"{self.root_path}/encoder_sj.ui" 
        ui_file = QFile(ui_file_path)
        self.ui = QUiLoader().load(ui_file,self)
        
app = QApplication()
win = EncoderTest()
win.show()
app.exec()

            
        