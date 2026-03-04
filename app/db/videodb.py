"""  
Database Module
Handles database operations for video storage using SQLAlchemy
"""
from pathlib import Path
from app.core.config import settings
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy import or_

from app.db.session import SessionLocal
from app.models.video import Video

def format_relative_time(timestamp: Any) -> str:
    """
    Format ISO timestamp or datetime object to human-readable relative time
    """
    try:
        if isinstance(timestamp, str):
            created = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        elif isinstance(timestamp, datetime):
            created = timestamp
        else:
            return "unknown time"
            
        now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
        diff = now - created
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
    except Exception as e:
        print(f"Error formatting timestamp: {e}")
        return "unknown time"


def _video_model_to_dict(video: Video) -> Dict:
    """Helper to convert Video SQLAlchemy model to dictionary"""
    result = {
        'id': video.id,
        'user_id': video.user_id,
        'music_id': video.music_id,
        'title': video.title,
        'category': video.category,
        'format': video.format,
        'style': video.style,
        'voice': video.voice,
        'script': video.script,
        'keywords': video.keywords,
        'negative_keywords': video.negative_keywords,
        'path': video.path,
        'thumbnail_path': video.thumbnail_path,
        'duration': video.duration,
        'status': video.status,
        'media_option': video.media_option,
    }
    
    # Ensure created_at is converted to ISO format string for consistency with old behavior
    if video.created_at:
        result['created_at'] = video.created_at.isoformat()
    else:
        result['created_at'] = None
        
    return result


class VideoDatabase:
    """Manage video records in PostgreSQL database via SQLAlchemy"""
    
    def __init__(self, db_path: Path = None):
        """Initialize database connection"""
        # db_path is ignored now since we use SQLAlchemy and DATABASE_URL
        pass
        
    def add_video(self, video_data: Dict) -> int:
        try:
            db = SessionLocal()
            print(f"💾 Saving to PostgreSQL database: {video_data.get('title')}")
            print(f"   Path: {video_data.get('path')}")
            
            created_at_dt = None
            if 'created_at' in video_data:
                try:
                    created_at_dt = datetime.fromisoformat(video_data['created_at'].replace('Z', '+00:00'))
                    # Remove timezone info for naive timestamp if timezone is used
                    if created_at_dt.tzinfo:
                        created_at_dt = created_at_dt.replace(tzinfo=None)
                except ValueError:
                    pass
            
            if not created_at_dt:
                created_at_dt = datetime.utcnow()

            db_video = Video(
                user_id=video_data.get('user_id'),
                music_id=video_data.get('music_id'),
                title=video_data.get('title'),
                category=video_data.get('category'),
                format=video_data.get('format'),
                style=video_data.get('style'),
                voice=video_data.get('voice'),
                script=video_data.get('script', ''),
                keywords=video_data.get('keywords', ''),
                negative_keywords=video_data.get('negative_keywords', ''),
                path=video_data.get('path'),
                duration=float(video_data.get('duration', 0.0)) if video_data.get('duration') else 0.0,
                status=video_data.get('status', 'completed'),
                media_option=video_data.get('media_option', 'all_images'),
                created_at=created_at_dt
            )
            
            db.add(db_video)
            db.commit()
            db.refresh(db_video)
            video_id = db_video.id
            db.close()
            
            print(f"✓ Saved to database with ID: {video_id}")
            return video_id
        except Exception as e:
            print(f"✗ Database save error: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def get_video(self, video_id: int) -> Optional[Dict]:
        db = SessionLocal()
        video = db.query(Video).filter(Video.id == video_id).first()
        db.close()
        
        if video:
            return _video_model_to_dict(video)
        return None
    
    def get_all_videos(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        try:
            db = SessionLocal()
            videos_obj = db.query(Video).order_by(Video.created_at.desc()).offset(offset).limit(limit).all()
            db.close()
            
            videos = []
            for v in videos_obj:
                video_dict = _video_model_to_dict(v)
                
                # Add formatted relative time
                if v.created_at:
                    video_dict['created_at_relative'] = format_relative_time(v.created_at)
                    
                # Verify file still exists
                video_path = Path(video_dict.get('path', ''))
                video_dict['file_exists'] = video_path.exists()
                if not video_dict['file_exists']:
                    print(f"⚠️ Warning: Video file missing for ID {video_dict['id']}: {video_path}")
                
                videos.append(video_dict)
                
            print(f"📋 Retrieved {len(videos)} videos from database")
            return videos
            
        except Exception as e:
            print(f"✗ Error retrieving videos from database: {e}")
            import traceback
            traceback.print_exc()
            return []
            
    def update_video(self, video_id: int, updates: Dict) -> bool:
        db = SessionLocal()
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            db.close()
            return False
            
        for key, value in updates.items():
            if key != 'id' and hasattr(video, key):
                setattr(video, key, value)
                
        db.commit()
        db.close()
        return True
        
    def delete_video(self, video_id: int) -> bool:
        db = SessionLocal()
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            db.close()
            return False
            
        db.delete(video)
        db.commit()
        db.close()
        return True
        
    def search_videos(self, query: str) -> List[Dict]:
        db = SessionLocal()
        search_pattern = f"%{query}%"
        videos_obj = db.query(Video).filter(
            or_(
                Video.title.ilike(search_pattern),
                Video.category.ilike(search_pattern)
            )
        ).order_by(Video.created_at.desc()).all()
        db.close()
        
        return [_video_model_to_dict(v) for v in videos_obj]
        
    def get_video_count(self) -> int:
        db = SessionLocal()
        count = db.query(Video).count()
        db.close()
        return count
        
    def clear_all_videos(self) -> int:
        db = SessionLocal()
        count = db.query(Video).count()
        db.query(Video).delete()
        db.commit()
        db.close()
        return count


if __name__ == "__main__":
    # Test the database connection
    db = VideoDatabase()
    print(f"Database initialized and connected")
    try:
        print(f"Total videos: {db.get_video_count()}")
    except Exception as e:
        print(f"Connection failed: {e}")
