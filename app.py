import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from apify_client import ApifyClient

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Enable CORS to allow your React app to talk to this Python app
CORS(app) 

# Initialize Apify Client from Environment Variable
# You will set this in Render Dashboard later
APIFY_TOKEN = os.environ.get('APIFY_TOKEN')
ACTOR_ID = 'clockworks/tiktok-scraper'

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "active", "service": "T1ERA Trend Intelligence"}), 200

@app.route('/api/analyze-trends', methods=['POST'])
def analyze_trends():
    if not APIFY_TOKEN:
        logger.error("APIFY_TOKEN is missing in environment variables")
        return jsonify({"error": "Server misconfiguration"}), 500

    try:
        data = request.json
        keywords = data.get('keywords', 'trending')
        
        logger.info(f"Received analysis request for: {keywords}")

        client = ApifyClient(APIFY_TOKEN)

        # 1. Run the Actor
        run_input = {
            "search": keywords,
            "resultsPerPage": 15,
            "excludePinnedPosts": True,
            "searchSection": "top",
        }

        # Run synchronously (for simplicity in this prototype)
        # In a high-scale app, you might use webhooks, but this is fine for now.
        run = client.actor(ACTOR_ID).call(run_input=run_input)

        if not run:
            return jsonify({"error": "Apify run failed to start"}), 500

        # 2. Fetch Results
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items

        if not dataset_items:
            return jsonify({"error": "No data found"}), 404

        # 3. Process Data (Python Version of your TypeScript Logic)
        hashtags_map = {}
        total_views = 0
        max_plays = -1
        top_video = None

        for item in dataset_items:
            # Aggregate Hashtags
            tags = item.get('hashtags', [])
            for tag in tags:
                name = tag.get('name')
                if name:
                    hashtags_map[name] = hashtags_map.get(name, 0) + 1
            
            # Aggregate Stats
            stats = item.get('stats', {})
            # Handle different Apify output formats (sometimes stats.playCount, sometimes just playCount)
            plays = stats.get('playCount', item.get('playCount', 0))
            total_views += plays
            
            # Find Best Video
            if plays > max_plays:
                max_plays = plays
                top_video = {
                    "description": item.get('text', item.get('desc', '')),
                    "play_count": plays,
                    "url": item.get('webVideoUrl', item.get('videoUrl', '')),
                    "author_name": item.get('authorMeta', {}).get('name', item.get('author', {}).get('uniqueId', 'Unknown')),
                    "cover_url": item.get('videoMeta', {}).get('coverUrl', item.get('cover', ''))
                }

        # Sort Hashtags
        sorted_tags = sorted(hashtags_map.items(), key=lambda x: x[1], reverse=True)
        formatted_tags = []
        for tag, count in sorted_tags[:5]:
            formatted_tags.append({
                "tag": f"#{tag}",
                "views": "N/A", 
                "usage_count": count,
                "growth": "viral" if count > 3 else "stable"
            })

        # Competition Logic
        volume = len(dataset_items)
        competition = "High" if volume >= 15 else "Medium" if volume > 5 else "Low"

        # Format Total Views
        if total_views > 1000000:
            views_str = f"{total_views/1000000:.1f}M"
        else:
            views_str = f"{total_views/1000:.1f}K"

        response_data = {
            "trending_hashtags": formatted_tags,
            "top_videos": [top_video] if top_video else [],
            "niche_stats": {
                "total_posts": volume,
                "competition_level": competition
            },
            "sample_caption": top_video['description'] if top_video else "",
            "total_niche_views": views_str
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Render provides a PORT env var
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
