#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mv2tvdir - 将电视剧文件移动到按剧名/季级组织的目录结构中

用法：
    mv2tvdir.py <源目录> <目标目录>

示例：
    mv2tvdir.py /downloads /media/tv
"""

import os
import sys
import re
import shutil
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 支持的视频和字幕文件扩展名
VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.avi')
SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub')
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS + SUBTITLE_EXTENSIONS

# 正则表达式模式，用于从文件名中提取剧名和季数
# 例如："Invasion.2021.S03E04.1080p.x265-ELiTE"
SEASON_PATTERN = re.compile(r'[.\s][Ss]([0-9]{1,2})[Ee][0-9]{1,2}[.\s]')
YEAR_PATTERN = re.compile(r'[.\s](19[0-9]{2}|20[0-9]{2})[.\s]')


def extract_show_info(filename):
    """
    从文件名中提取剧名和季数
    
    Args:
        filename: 文件名
        
    Returns:
        tuple: (剧名, 季数) 或者 (None, None) 如果无法提取
    """
    # 移除文件扩展名
    basename = os.path.splitext(filename)[0]
    
    # 提取季数
    season_match = SEASON_PATTERN.search(basename)
    if not season_match:
        logging.warning(f"无法从 {filename} 中提取季数")
        return None, None
    
    season_num = int(season_match.group(1))
    season_str = f"S{season_num:02d}"
    
    # 提取剧名（假设剧名在年份之前或季数之前）
    year_match = YEAR_PATTERN.search(basename)
    
    if year_match:
        # 如果有年份，剧名在年份之前
        show_name_parts = basename[:year_match.start()].split('.')
    else:
        # 否则，剧名在季数之前
        show_name_parts = basename[:season_match.start()].split('.')
    
    # 清理剧名
    show_name = ' '.join(show_name_parts).strip()
    if not show_name:
        logging.warning(f"无法从 {filename} 中提取剧名")
        return None, None
    
    return show_name, season_str


def create_target_directory(base_dir, show_name, season):
    """
    创建目标目录结构：剧名/季级/
    
    Args:
        base_dir: 基础目录
        show_name: 剧名
        season: 季数
        
    Returns:
        str: 创建的目标目录路径
    """
    # 创建剧名目录
    show_dir = os.path.join(base_dir, show_name)
    if not os.path.exists(show_dir):
        os.makedirs(show_dir)
        logging.info(f"创建剧名目录: {show_dir}")
    
    # 创建季目录
    season_dir = os.path.join(show_dir, season)
    if not os.path.exists(season_dir):
        os.makedirs(season_dir)
        logging.info(f"创建季目录: {season_dir}")
    
    return season_dir


def move_file(source_path, target_dir):
    """
    将文件移动到目标目录
    
    Args:
        source_path: 源文件路径
        target_dir: 目标目录
        
    Returns:
        bool: 是否成功移动文件
    """
    filename = os.path.basename(source_path)
    target_path = os.path.join(target_dir, filename)
    
    # 检查目标文件是否已存在
    if os.path.exists(target_path):
        logging.warning(f"目标文件已存在: {target_path}")
        return False
    
    try:
        shutil.move(source_path, target_path)
        logging.info(f"移动文件: {source_path} -> {target_path}")
        return True
    except Exception as e:
        logging.error(f"移动文件失败: {source_path} -> {target_path}, 错误: {e}")
        return False


def process_directory(source_dir, target_base_dir):
    """
    处理源目录中的所有文件
    
    Args:
        source_dir: 源目录
        target_base_dir: 目标基础目录
        
    Returns:
        tuple: (成功数, 失败数)
    """
    success_count = 0
    failure_count = 0
    
    # 遍历源目录中的所有文件
    for root, _, files in os.walk(source_dir):
        for filename in files:
            # 检查文件扩展名是否受支持
            _, ext = os.path.splitext(filename)
            if ext.lower() not in SUPPORTED_EXTENSIONS:
                continue
            
            source_path = os.path.join(root, filename)
            
            # 提取剧名和季数
            show_name, season = extract_show_info(filename)
            if not show_name or not season:
                logging.warning(f"跳过文件: {filename} (无法提取信息)")
                failure_count += 1
                continue
            
            # 创建目标目录
            target_dir = create_target_directory(target_base_dir, show_name, season)
            
            # 移动文件
            if move_file(source_path, target_dir):
                success_count += 1
            else:
                failure_count += 1
    
    return success_count, failure_count


def main():
    # 检查命令行参数
    if len(sys.argv) != 3:
        print(f"用法: {sys.argv[0]} <源目录> <目标目录>")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    target_dir = sys.argv[2]
    
    # 检查源目录和目标目录是否存在
    if not os.path.isdir(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        sys.exit(1)
    
    if not os.path.isdir(target_dir):
        print(f"错误: 目标目录不存在: {target_dir}")
        sys.exit(1)
    
    logging.info(f"开始处理: 源目录 = {source_dir}, 目标目录 = {target_dir}")
    
    # 处理目录
    success_count, failure_count = process_directory(source_dir, target_dir)
    
    logging.info(f"处理完成: 成功 = {success_count}, 失败 = {failure_count}")


if __name__ == "__main__":
    main()