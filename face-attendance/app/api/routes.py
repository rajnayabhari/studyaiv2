from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from ..auth.decorators import role_required
from ..services.enrollment import process_enrollment_frame, decode_base64_image

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/enroll/<int:student_id>/capture', methods=['POST'])
@login_required
@role_required('admin')
def enroll_capture(student_id):
    data = request.json
    if not data or 'image' not in data:
        return jsonify({'success': False, 'message': 'No image provided'}), 400
        
    try:
        img_bgr = decode_base64_image(data['image'])
        success, msg, template_id = process_enrollment_frame(student_id, img_bgr, current_app.config)
        return jsonify({
            'success': success,
            'message': msg,
            'template_id': template_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
