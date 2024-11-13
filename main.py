from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import random
import mysql.connector
from mysql.connector import Error
import json

app = FastAPI()

# 템플릿 디렉토리 설정
templates = Jinja2Templates(directory="templates")

# 'static' 디렉토리에서 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")

# Spotify API 설정
cid = '3df9f8aff5b7484dbb08af724c52ff5d'
secret = '4e2f84d79f914f83b34a7fedbf4d2ab1'
redirect_uri = 'http://localhost:8888/callback'
client = Spotify(auth_manager=SpotifyOAuth(client_id=cid, client_secret=secret, redirect_uri=redirect_uri))

# 로컬 저장소 파일 경로
DATA_FILE = "user_data.json"

def load_user_data():
    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


# 로컬 파일에 데이터 저장하기
def save_user_data(new_data):
    # 기존 데이터 로드
    try:
        with open(DATA_FILE, "r") as file:
            existing_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = {}

    # 기존 데이터와 새로운 데이터 병합
    existing_data.update(new_data)

    # 병합된 데이터를 파일에 저장
    with open(DATA_FILE, "w") as file:
        json.dump(existing_data, file, indent=4)
    print("User data updated and saved:", existing_data)


# 초기 데이터 로드
user_data_store = load_user_data()
logged_in_user = None

# 가상의 DB 대체용 데이터 저장소
user_data_store = {}
logged_in_user = None

# 기본 홈 페이지 라우팅
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 로그인 페이지 라우팅
@app.get("/login")  
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "message": ""})

@app.post("/login")
async def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    global logged_in_user, user_data_store
    user_data_store = load_user_data()  # 최신 데이터 로드
    user = user_data_store.get(email)

    if user and user["password"] == password:
        logged_in_user = email  # 로그인 성공
        return RedirectResponse(url="/recommendations", status_code=303)
    else:
        message = "Invalid email or password."
        return templates.TemplateResponse("login.html", {"request": request, "message": message})


# 회원가입 페이지 라우팅
@app.get("/register")
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register_post(request: Request, email: str = Form(...), password: str = Form(...),
                        confirm_password: str = Form(...)):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match!")

    if email in user_data_store:
        raise HTTPException(status_code=400, detail="Email already registered.")

    user_data_store[email] = {
        "password": password,
        "recommendations": []
    }
    save_user_data(user_data_store)
    return RedirectResponse(url="/login", status_code=303)

# 추천 시스템 페이지 라우팅 (로그인 후 접근)
@app.get("/recommendations", response_class=HTMLResponse)
async def get_features_form(request: Request):
    if logged_in_user is None:
        raise HTTPException(status_code=403, detail="You must be logged in to access this page.")
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/recommendations")
async def recommend_songs(
    request: Request,
    danceability: float = Form(...),
    energy: float = Form(...),
    instrumentalness: float = Form(...),
    valence: float = Form(...),
    tempo: float = Form(...),
    acousticness: float = Form(...),
):
    if logged_in_user is None:
        raise HTTPException(status_code=403, detail="You must be logged in to recommend songs.")

    # 사용자가 입력한 feature 값으로 딕셔너리 생성
    features = {
        "danceability": danceability,
        "energy": energy,
        "instrumentalness": instrumentalness,
        "valence": valence,
        "tempo": tempo,
        "acousticness": acousticness
    }

    try:
        # Spotify API로 곡 추천
        recommendations = client.recommendations(seed_genres=['k-pop'], **features, limit=10)
        songs = []
        for track in recommendations['tracks']:
            try:
                song_name = track['name']
                artist = track['artists'][0]['name']
                song_id = track['id']
                spotify_url = f"https://open.spotify.com/embed/track/{song_id}"
                songs.append({"song_name": song_name, "artist": artist, "url": spotify_url})
            except KeyError as e:
                print(f"KeyError: {e}")
                continue
            
            print("Recommended Songs:", songs)



        # 추천 내역 저장
        user_data_store[logged_in_user]["recommendations"].extend(songs)
        save_user_data(user_data_store)

        # 템플릿으로 전달
        return templates.TemplateResponse("recommendations.html", {"request": request, "recommended_songs": songs})


    except Exception as e:
        print(f"Error while fetching recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recommendations.")
