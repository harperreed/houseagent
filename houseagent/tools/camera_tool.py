# ABOUTME: Camera snapshot tool for capturing images from RTSP cameras
# ABOUTME: Provides snapshot capability for zones based on floor plan camera mapping

import os
import subprocess
import tempfile
import base64
from typing import Dict, Any
import structlog
from openai import OpenAI
from houseagent.floor_plan import FloorPlanModel


class CameraTool:
    """Tool for capturing camera snapshots from RTSP streams"""

    def __init__(self, floor_plan: FloorPlanModel):
        self.logger = structlog.get_logger(__name__)
        self.floor_plan = floor_plan

        # Initialize OpenAI client if API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=api_key) if api_key else None

        # Load vision prompt
        prompt_path = os.getenv("CAMERA_VISION_PROMPT", "prompts/camera_vision.txt")
        try:
            with open(prompt_path) as f:
                self.vision_prompt_template = f.read()
        except FileNotFoundError:
            self.logger.warning(f"Camera vision prompt not found: {prompt_path}")
            self.vision_prompt_template = """You are analyzing a security camera snapshot from {camera_name} in the {zone_name} area.

Describe what you see in 1-2 concise sentences. Focus on:
- People: How many, what they're doing
- Activity: Normal office work vs unusual behavior
- Objects: Anything out of place or noteworthy
- Safety concerns: Any hazards or security issues

Be direct and specific. Skip pleasantries."""

        # Check if cameras have RTSP URLs configured
        if not self.floor_plan.cameras or not any(
            c.get("rtsp") for c in self.floor_plan.cameras
        ):
            self.logger.warning("No cameras with RTSP URLs configured in floor plan")

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Capture snapshot from camera

        Params:
            zone_id: Zone to capture (uses first camera in zone)
            camera_id: Specific camera ID (optional, overrides zone_id)
        """
        zone_id = params.get("zone_id")
        camera_id = params.get("camera_id")

        # Find camera
        camera = None
        if camera_id:
            camera = next(
                (c for c in self.floor_plan.cameras if c["id"] == camera_id), None
            )
        elif zone_id:
            cameras = [c for c in self.floor_plan.cameras if c.get("zone") == zone_id]
            camera = cameras[0] if cameras else None

        if not camera:
            return {
                "success": False,
                "error": f"No camera found for zone={zone_id}, camera_id={camera_id}",
            }

        # Get RTSP URL from camera config
        rtsp_url = camera.get("rtsp")
        if not rtsp_url:
            return {
                "success": False,
                "error": f"Camera {camera['id']} has no RTSP URL configured",
            }

        try:
            # Use ffmpeg to capture snapshot
            snapshot_path = self._capture_snapshot(rtsp_url)

            # Analyze image with vision model
            analysis = self._analyze_image(snapshot_path, camera)

            return {
                "success": True,
                "camera_id": camera["id"],
                "camera_name": camera.get("name", camera["id"]),
                "zone": camera["zone"],
                "snapshot_path": snapshot_path,
                "analysis": analysis,
                "message": f"Snapshot from {camera.get('name', camera['id'])} in {camera['zone']}: {analysis}",
            }
        except Exception as e:
            self.logger.error(
                "Camera snapshot failed", camera_id=camera["id"], error=str(e)
            )
            return {
                "success": False,
                "error": f"Failed to capture snapshot: {str(e)}",
            }

    def _capture_snapshot(self, rtsp_url: str) -> str:
        """Capture single frame from RTSP stream using ffmpeg"""
        # Create temp file for snapshot
        fd, snapshot_path = tempfile.mkstemp(suffix=".jpg", prefix="camera_")
        os.close(fd)

        # FFmpeg command to capture single frame
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-rtsp_transport",
            "tcp",  # Use TCP for reliability
            "-i",
            rtsp_url,
            "-vframes",
            "1",  # Capture 1 frame
            "-q:v",
            "2",  # High quality
            snapshot_path,
        ]

        # Run ffmpeg with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,  # 10 second timeout
            check=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")

        return snapshot_path

    def _analyze_image(self, image_path: str, camera: Dict) -> str:
        """Analyze snapshot using GPT-5 vision model"""
        # Skip analysis if OpenAI client not available
        if not self.openai_client:
            self.logger.warning(
                "OpenAI API key not configured, skipping image analysis"
            )
            return "Image captured (vision analysis disabled - no API key)"

        try:
            # Read and encode image as base64
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")

            # Build context-aware prompt
            zone_name = camera.get("zone", "unknown")
            camera_name = camera.get("name", camera["id"])

            prompt = self.vision_prompt_template.format(
                camera_name=camera_name, zone_name=zone_name
            )

            # Call GPT-5 vision using Responses API
            response = self.openai_client.responses.create(
                model=os.getenv("SYNTHESIS_MODEL", "gpt-5"),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{image_data}",
                            },
                        ],
                    }
                ],
            )

            analysis = response.output_text.strip()
            self.logger.info(
                "Image analyzed", camera_id=camera["id"], analysis=analysis
            )
            return analysis

        except Exception as e:
            self.logger.error("Image analysis failed", error=str(e))
            return "Image captured but analysis failed"

    def get_description(self) -> str:
        """Tool description for AI"""
        available_cameras = ", ".join(
            [f"{c['id']} ({c['zone']})" for c in self.floor_plan.cameras]
        )
        return f"""Capture snapshot from security camera.

        Available cameras: {available_cameras}

        Usage:
        - get_camera_snapshot(zone_id="hack_area") - snapshot from zone's first camera
        - get_camera_snapshot(camera_id="hack_area") - snapshot from specific camera

        Returns path to JPEG snapshot file."""
