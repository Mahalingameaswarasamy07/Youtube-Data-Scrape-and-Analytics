from googleapiclient.discovery import build
import re
import pymongo
import mysql.connector
import sqlalchemy
from sqlalchemy import create_engine
import pymysql
import pandas as pd
import streamlit as st
import plotly.express as px


st.set_page_config(layout='wide')
st.title('Youtube Data Scrape')

channel_id = st.text_input('Youtube channel Id')
Get_data = st.button(':red[GET DATA]')

if "Get_state" not in st.session_state:
    st.session_state.Get_state = False
if Get_data or st.session_state.Get_state:
    st.session_state.Get_state = True

    api_service_name = 'youtube'
    api_version = 'v3'
    api_key = 'YOUR API KEY'
    youtube = build(api_service_name,api_version,developerKey =api_key)

    
    def get_channel_data(youtube,channel_id):
        try:
            try:
                channel_request = youtube.channels().list(
                    part = 'snippet,statistics,contentDetails',
                    id = channel_id)
                channel_response = channel_request.execute()
                
                if 'items' not in channel_response:
                    st.write(f"Invalid channel id: {channel_id}")
                    st.error("Enter the correct 11-digit **channel_id**")
                    return None
                
                return channel_response
            
            except HttpError as e:
                st.error('Server error (or) Check your internet connection (or) Please Try again after a few minutes', icon='🚨')
                st.write('An error occurred: %s' % e)
                return None
        except:
            st.write('You have exceeded your YouTube API quota. Please try again tomorrow.')

    channel_data = get_channel_data(youtube,channel_id)

    channel_name = channel_data['items'][0]['snippet']['title']
    channel_video_count = channel_data['items'][0]['statistics']['videoCount']
    channel_subscriber_count = channel_data['items'][0]['statistics']['subscriberCount']
    channel_view_count = channel_data['items'][0]['statistics']['viewCount']
    channel_description = channel_data['items'][0]['snippet']['description']
    channel_playlist_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    channel = {
        "Channel_Details": {
            "Channel_Name": channel_name,
            "Channel_Id": channel_id,
            "Video_Count": channel_video_count,
            "Subscriber_Count": channel_subscriber_count,
            "Channel_Views": channel_view_count,
            "Channel_Description": channel_description,
            "Playlist_Id": channel_playlist_id
        }
    }

    def get_video_ids(youtube, channel_playlist_id):
        
        video_id = []
        next_page_token = None
        while True:
            request = youtube.playlistItems().list(
                part='contentDetails',
                playlistId=channel_playlist_id,
                maxResults=50,
                pageToken=next_page_token)
            response = request.execute()

            for item in response['items']:
                video_id.append(item['contentDetails']['videoId'])

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        return video_id

    video_ids = get_video_ids(youtube, channel_playlist_id)

    def get_video_data(youtube, video_ids):
        
        video_data = []
        for video_id in video_ids:
            try:
                request = youtube.videos().list(
                    part='snippet, statistics, contentDetails',
                    id=video_id)
                response = request.execute()

                video = response['items'][0]
                try:
                    video['comment_threads'] = get_video_comments(youtube, video_id, max_comments=2)
                except:
                    video['comment_threads'] = None
                duration = video.get('contentDetails', {}).get('duration', 'Not Available')
                if duration != 'Not Available':
                    duration = convert_duration(duration)
                video['contentDetails']['duration'] = duration    
                video_data.append(video)
            except:
                st.write('You have exceeded your YouTube API quota. Please try again tomorrow.')
        return video_data

    def get_video_comments(youtube, video_id, max_comments):
        request = youtube.commentThreads().list(
            part='snippet',
            maxResults=max_comments,
            textFormat="plainText",
            videoId=video_id)
        response = request.execute()
        return response

    def convert_duration(duration):
        regex = r'PT(\d+H)?(\d+M)?(\d+S)?'
        match = re.match(regex, duration)
        if not match:
            return '00:00:00'
        hours, minutes, seconds = match.groups()
        hours = int(hours[:-1]) if hours else 0
        minutes = int(minutes[:-1]) if minutes else 0
        seconds = int(seconds[:-1]) if seconds else 0
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return '{:02d}:{:02d}:{:02d}'.format(int(total_seconds / 3600), int((total_seconds % 3600) / 60), int(total_seconds % 60))

    video_data = get_video_data(youtube, video_ids)
    videos = {}
    for i, video in enumerate (video_data):
        video_id = video['id']
        video_name = video['snippet']['title']
        video_description = video['snippet']['description']
        tags = video['snippet'].get('tags', [])
        published_at = video['snippet']['publishedAt']
        view_count = video['statistics']['viewCount']
        like_count = video['statistics'].get('likeCount', 0)
        dislike_count = video['statistics'].get('dislikeCount', 0)
        favorite_count = video['statistics'].get('favoriteCount', 0)
        comment_count = video['statistics'].get('commentCount', 0)
        duration = video.get('contentDetails', {}).get('duration', 'Not Available')
        thumbnail = video['snippet']['thumbnails']['high']['url']
        caption_status = video.get('contentDetails', {}).get('caption', 'Not Available')
        comments = 'Unavailable'

        if video['comment_threads'] is not None:
            comments = {}
            for index, comment_thread in enumerate(video['comment_threads']['items']):
                comment = comment_thread['snippet']['topLevelComment']['snippet']
                comment_id = comment_thread['id']
                comment_text = comment['textDisplay']
                comment_author = comment['authorDisplayName']
                comment_published_at = comment['publishedAt']
                comments[f"Comment_Id_{index + 1}"] = {
                    'Comment_Id': comment_id,
                    'Comment_Text': comment_text,
                    'Comment_Author': comment_author,
                    'Comment_PublishedAt': comment_published_at
                }
                   
        videos[f"Video_Id_{i + 1}"] = {
            'Video_Id': video_id,
            'Video_Name': video_name,
            'Video_Description': video_description,
            'Tags': tags,
            'PublishedAt': published_at,
            'View_Count': view_count,
            'Like_Count': like_count,
            'Dislike_Count': dislike_count,
            'Favorite_Count': favorite_count,
            'Comment_Count': comment_count,
            'Duration': duration,
            'Thumbnail': thumbnail,
            'Caption_Status': caption_status,
            'Comments': comments
        }

    final_output = {**channel, **videos}

    client = pymongo.MongoClient('mongodb://localhost:27017/')
    mydb = client['youtube_scrape_db']
    collection = mydb['Youtube_data']
    final_output_data = {
        'Channel_Name': channel_name,
        "Channel_data":final_output
        }

    upload = collection.replace_one({'_id': channel_id}, final_output_data, upsert=True)
    st.write(f"Updated document id: {upload.upserted_id if upload.upserted_id else upload.modified_count}")
    client.close()


client = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = client['youtube_scrape_db']
collection = mydb['Youtube_data']
document_names = []
for document in collection.find():
    document_names.append(document["Channel_Name"])
document_name = st.selectbox('**Select Channel name**', options = document_names, key='document_names')
Migrate = st.button(':red[MIGRATE TO MYSQL]')

if 'migrate_sql' not in st.session_state:
    st.session_state_migrate_sql = False
if Migrate or st.session_state_migrate_sql:
    st.session_state_migrate_sql = True

    result = collection.find_one({"Channel_Name": document_name})
    client.close()

    channel_details_to_sql = {
        "Channel_Name": result['Channel_Name'],
        "Channel_Id": result['_id'],
        "Video_Count": result['Channel_data']['Channel_Details']['Video_Count'],
        "Subscriber_Count": result['Channel_data']['Channel_Details']['Subscriber_Count'],
        "Channel_Views": result['Channel_data']['Channel_Details']['Channel_Views'],
        "Channel_Description": result['Channel_data']['Channel_Details']['Channel_Description'],
        "Playlist_Id": result['Channel_data']['Channel_Details']['Playlist_Id']
        }
    channel_df = pd.DataFrame.from_dict(channel_details_to_sql, orient='index').T
            
    playlist_tosql = {"Channel_Id": result['_id'],
                    "Playlist_Id": result['Channel_data']['Channel_Details']['Playlist_Id']
                    }
    playlist_df = pd.DataFrame.from_dict(playlist_tosql, orient='index').T

    video_details_list = []
    for i in range(1,len(result['Channel_data'])-1):
        video_details_tosql = {
            'Playlist_Id':result['Channel_data']['Channel_Details']['Playlist_Id'],
            'Video_Id': result['Channel_data'][f"Video_Id_{i}"]['Video_Id'],
            'Video_Name': result['Channel_data'][f"Video_Id_{i}"]['Video_Name'],
            'Video_Description': result['Channel_data'][f"Video_Id_{i}"]['Video_Description'],
            'Published_date': result['Channel_data'][f"Video_Id_{i}"]['PublishedAt'],
            'View_Count': result['Channel_data'][f"Video_Id_{i}"]['View_Count'],
            'Like_Count': result['Channel_data'][f"Video_Id_{i}"]['Like_Count'],
            'Dislike_Count': result['Channel_data'][f"Video_Id_{i}"]['Dislike_Count'],
            'Favorite_Count': result['Channel_data'][f"Video_Id_{i}"]['Favorite_Count'],
            'Comment_Count': result['Channel_data'][f"Video_Id_{i}"]['Comment_Count'],
            'Duration': result['Channel_data'][f"Video_Id_{i}"]['Duration'],
            'Thumbnail': result['Channel_data'][f"Video_Id_{i}"]['Thumbnail'],
            'Caption_Status': result['Channel_data'][f"Video_Id_{i}"]['Caption_Status']
            }
        video_details_list.append(video_details_tosql)
    video_df = pd.DataFrame(video_details_list)

    Comment_details_list = []
    for i in range(1, len(result['Channel_data']) - 1):
        comments_access = result['Channel_data'][f"Video_Id_{i}"]['Comments']
        if comments_access == 'Unavailable' or ('Comment_Id_1' not in comments_access or 'Comment_Id_2' not in comments_access) :
            Comment_details_tosql = {
                'Video_Id': 'Unavailable',
                'Comment_Id': 'Unavailable',
                'Comment_Text': 'Unavailable',
                'Comment_Author':'Unavailable',
                'Comment_Published_date': 'Unavailable',
                }
            Comment_details_list.append(Comment_details_tosql)
            
        else:
            for j in range(1,3):
                Comment_details_tosql = {
                'Video_Id': result['Channel_data'][f"Video_Id_{i}"]['Video_Id'],
                'Comment_Id': result['Channel_data'][f"Video_Id_{i}"]['Comments'][f"Comment_Id_{j}"]['Comment_Id'],
                'Comment_Text': result['Channel_data'][f"Video_Id_{i}"]['Comments'][f"Comment_Id_{j}"]['Comment_Text'],
                'Comment_Author': result['Channel_data'][f"Video_Id_{i}"]['Comments'][f"Comment_Id_{j}"]['Comment_Author'],
                'Comment_Published_date': result['Channel_data'][f"Video_Id_{i}"]['Comments'][f"Comment_Id_{j}"]['Comment_PublishedAt'],
                }
                Comment_details_list.append(Comment_details_tosql)
    Comments_df = pd.DataFrame(Comment_details_list)

    connect = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "mysqlpassword1!",
    auth_plugin = "mysql_native_password")
    mycursor = connect.cursor()
    mycursor.execute("CREATE DATABASE IF NOT EXISTS youtube_scrape_db")
    mycursor.close()
    connect.close()
    engine = create_engine('mysql+mysqlconnector://root:mysqlpassword1!@localhost/youtube_scrape_db', echo=False)

    channel_df.to_sql('channel', engine, if_exists='append', index=False,
                    dtype = {"Channel_Name": sqlalchemy.types.VARCHAR(length=225),
                            "Channel_Id": sqlalchemy.types.VARCHAR(length=225),
                            "Video_Count": sqlalchemy.types.INT,
                            "Subscriber_Count": sqlalchemy.types.BigInteger,
                            "Channel_Views": sqlalchemy.types.BigInteger,
                            "Channel_Description": sqlalchemy.types.TEXT,
                            "Playlist_Id": sqlalchemy.types.VARCHAR(length=225),})

    playlist_df.to_sql('playlist', engine, if_exists='append', index=False,
                    dtype = {"Channel_Id": sqlalchemy.types.VARCHAR(length=225),
                                "Playlist_Id": sqlalchemy.types.VARCHAR(length=225),})
    
    video_df.to_sql('video', engine, if_exists='append', index=False,
                dtype = {'Playlist_Id': sqlalchemy.types.VARCHAR(length=225),
                        'Video_Id': sqlalchemy.types.VARCHAR(length=225),
                        'Video_Name': sqlalchemy.types.VARCHAR(length=225),
                        'Video_Description': sqlalchemy.types.TEXT,
                        'Published_date': sqlalchemy.types.String(length=50),
                        'View_Count': sqlalchemy.types.BigInteger,
                        'Like_Count': sqlalchemy.types.BigInteger,
                        'Dislike_Count': sqlalchemy.types.INT,
                        'Favorite_Count': sqlalchemy.types.INT,
                        'Comment_Count': sqlalchemy.types.INT,
                        'Duration': sqlalchemy.types.VARCHAR(length=1024),
                        'Thumbnail': sqlalchemy.types.VARCHAR(length=225),
                        'Caption_Status': sqlalchemy.types.VARCHAR(length=225),})

    Comments_df.to_sql('comments', engine, if_exists='append', index=False,
                    dtype = {'Video_Id': sqlalchemy.types.VARCHAR(length=225),
                            'Comment_Id': sqlalchemy.types.VARCHAR(length=225),
                            'Comment_Text': sqlalchemy.types.TEXT,
                            'Comment_Author': sqlalchemy.types.VARCHAR(length=225),
                            'Comment_Published_date': sqlalchemy.types.String(length=50),})


engine = create_engine('mysql+mysqlconnector://root:mysqlpassword1!@localhost/youtube_scrape_db', echo=False)
query = "SELECT Channel_Name FROM channel;"
results = pd.read_sql(query, engine)
channel_names_fromsql = list(results['Channel_Name'])
df_at_sql = pd.DataFrame(channel_names_fromsql, columns=['Available channel data']).reset_index(drop=True)
df_at_sql.index += 1  
st.dataframe(df_at_sql)

question_tosql = st.selectbox('**Select your Question**',
('Most viewed videos',
'Top liked videos',
'Total likes and dis-likes for each video',
'Number of views for each channel',
'Videos published in 2022',
'View all channels and videos list',
'Total number of videos for each channel',
'Total number of comments on each video',
'Average duration of all videos in each channel',
'Top commented videos'), key = 'collection_question')

connect_for_question = pymysql.connect(host='localhost', user='root', password='mysqlpassword1!', db='youtube_scrape_db')
cursor = connect_for_question.cursor()

if question_tosql == 'View all channels and videos list':
    cursor.execute("SELECT channel.Channel_Name, video.Video_Name FROM channel JOIN playlist JOIN video ON channel.Channel_Id = playlist.Channel_Id AND playlist.Playlist_Id = video.Playlist_Id;")
    result_1 = cursor.fetchall()
    df1 = pd.DataFrame(result_1, columns=['Channel Name', 'Video Name']).reset_index(drop=True)
    df1.index += 1
    st.dataframe(df1)

elif question_tosql == 'Total number of videos for each channel':

    col1,col2 = st.columns(2)
    with col1:
        cursor.execute("SELECT Channel_Name, Video_Count FROM channel ORDER BY Video_Count DESC;")
        result_2 = cursor.fetchall()
        df2 = pd.DataFrame(result_2,columns=['Channel Name','Video Count']).reset_index(drop=True)
        df2.index += 1
        st.dataframe(df2)

    with col2:
        fig_vc = px.bar(df2, y='Video Count', x='Channel Name', text_auto='.2s', title="Total number of videos", )
        fig_vc.update_traces(textfont_size=16,marker_color='#E48E9E')
        fig_vc.update_layout(title_font_color='#FFFFFF',title_font=dict(size=25))
        st.plotly_chart(fig_vc,use_container_width=True)

elif question_tosql == 'Most viewed videos':

    col1,col2 = st.columns(2)
    with col1:
        cursor.execute("SELECT channel.Channel_Name, video.Video_Name, video.View_Count FROM channel JOIN playlist ON channel.Channel_Id = playlist.Channel_Id JOIN video ON playlist.Playlist_Id = video.Playlist_Id ORDER BY video.View_Count DESC LIMIT 10;")
        result_3 = cursor.fetchall()
        df3 = pd.DataFrame(result_3,columns=['Channel Name', 'Video Name', 'View count']).reset_index(drop=True)
        df3.index += 1
        st.dataframe(df3)

    with col2:
        fig_topvc = px.bar(df3, y='View count', x='Video Name', text_auto='.2s', title="Most viewed videos")
        fig_topvc.update_traces(textfont_size=16,marker_color='#E48E9E')
        fig_topvc.update_layout(title_font_color='#FFFFFF',title_font=dict(size=25))
        st.plotly_chart(fig_topvc,use_container_width=True)

elif question_tosql == 'Total number of comments on each video':
    cursor.execute("SELECT channel.Channel_Name, video.Video_Name, video.Comment_Count FROM channel JOIN playlist ON channel.Channel_Id = playlist.Channel_Id JOIN video ON playlist.Playlist_Id = video.Playlist_Id;")
    result_4 = cursor.fetchall()
    df4 = pd.DataFrame(result_4,columns=['Channel Name', 'Video Name', 'Comment count']).reset_index(drop=True)
    df4.index += 1
    st.dataframe(df4)

elif question_tosql == 'Top liked videos':
    cursor.execute("SELECT channel.Channel_Name, video.Video_Name, video.Like_Count FROM channel JOIN playlist ON channel.Channel_Id = playlist.Channel_Id JOIN video ON playlist.Playlist_Id = video.Playlist_Id ORDER BY video.Like_Count DESC;")
    result_5= cursor.fetchall()
    df5 = pd.DataFrame(result_5,columns=['Channel Name', 'Video Name', 'Like count']).reset_index(drop=True)
    df5.index += 1
    st.dataframe(df5)

elif question_tosql == 'Total likes and dis-likes for each video':
    cursor.execute("SELECT channel.Channel_Name, video.Video_Name, video.Like_Count, video.Dislike_Count FROM channel JOIN playlist ON channel.Channel_Id = playlist.Channel_Id JOIN video ON playlist.Playlist_Id = video.Playlist_Id ORDER BY video.Like_Count DESC;")
    result_6= cursor.fetchall()
    df6 = pd.DataFrame(result_6,columns=['Channel Name', 'Video Name', 'Like count','Dislike count']).reset_index(drop=True)
    df6.index += 1
    st.dataframe(df6)

elif question_tosql == 'Number of views for each channel':

    col1, col2 = st.columns(2)
    with col1:
        cursor.execute("SELECT Channel_Name, Channel_Views FROM channel ORDER BY Channel_Views DESC;")
        result_7= cursor.fetchall()
        df7 = pd.DataFrame(result_7,columns=['Channel Name', 'Total number of views']).reset_index(drop=True)
        df7.index += 1
        st.dataframe(df7)
    
    with col2:
        fig_topview = px.bar(df7, y='Total number of views', x='Channel Name', text_auto='.2s', title="Number of views for each channel", )
        fig_topview.update_traces(textfont_size=16,marker_color='#E48E9E')
        fig_topview.update_layout(title_font_color='#FFFFFF',title_font=dict(size=25))
        st.plotly_chart(fig_topview,use_container_width=True)

elif question_tosql == 'Videos published in 2022':
    cursor.execute("SELECT channel.Channel_Name, video.Video_Name, video.Published_date FROM channel JOIN playlist ON channel.Channel_Id = playlist.Channel_Id JOIN video ON playlist.Playlist_Id = video.Playlist_Id  WHERE EXTRACT(YEAR FROM Published_date) = 2022;")
    result_8= cursor.fetchall()
    df8 = pd.DataFrame(result_8,columns=['Channel Name','Video Name', 'Year 2022 only']).reset_index(drop=True)
    df8.index += 1
    st.dataframe(df8)

elif question_tosql == 'Average duration of all videos in each channel':
    cursor.execute("SELECT channel.Channel_Name, TIME_FORMAT(SEC_TO_TIME(AVG(TIME_TO_SEC(TIME(video.Duration)))), '%H:%i:%s') AS duration  FROM channel JOIN playlist ON channel.Channel_Id = playlist.Channel_Id JOIN video ON playlist.Playlist_Id = video.Playlist_Id GROUP by Channel_Name ORDER BY duration DESC ;")
    result_9= cursor.fetchall()
    df9 = pd.DataFrame(result_9,columns=['Channel Name','Average duration of videos (HH:MM:SS)']).reset_index(drop=True)
    df9.index += 1
    st.dataframe(df9)

elif question_tosql == 'Top commented videos':
    cursor.execute("SELECT channel.Channel_Name, video.Video_Name, video.Comment_Count FROM channel JOIN playlist ON channel.Channel_Id = playlist.Channel_Id JOIN video ON playlist.Playlist_Id = video.Playlist_Id ORDER BY video.Comment_Count DESC;")
    result_10= cursor.fetchall()
    df10 = pd.DataFrame(result_10,columns=['Channel Name','Video Name', 'Number of comments']).reset_index(drop=True)
    df10.index += 1
    st.dataframe(df10)

connect_for_question.close()