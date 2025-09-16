#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2023-2024 mv2tvdir Contributors
# 本项目采用MIT许可证 (MIT License)
# 详情请参阅项目根目录下的LICENSE文件

# 版本信息
__version__ = "1.0.1"

"""
mv2tvdir - 将电视剧文件移动到按剧名/季级组织的目录结构中

用法：
    mv2tvdir.py <源目录> <目标目录> [选项]

选项：
    --resolution=<分辨率>  只处理指定分辨率的文件 (例如: 1080p, 720p)
    --codec=<编码>        只处理指定编码的文件 (例如: x265, x264)
    --remove-source       移动文件后删除源目录（如果源目录为空或只剩下nfo、txt、jpg等文件）

示例：
    mv2tvdir.py /downloads /media/tv
    mv2tvdir.py /downloads /media/tv --resolution=1080p
    mv2tvdir.py /downloads /media/tv --codec=x265
    mv2tvdir.py /downloads /media/tv --resolution=1080p --codec=x265
    mv2tvdir.py /downloads /media/tv --remove-source
"""

import os
import sys
import re
import shutil
import logging
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 支持的视频和字幕文件扩展名
VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.avi')
SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub')
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS + SUBTITLE_EXTENSIONS

# 不需要删除的文件类型（在源目录中保留的文件类型）
IGNORED_EXTENSIONS = ('.nfo', '.txt', '.jpg', '.jpeg', '.png', '.gif')

# 正则表达式模式，用于从文件名中提取剧名和季数
# 例如："Invasion.2021.S03E04.1080p.x265-ELiTE"
SEASON_PATTERN = re.compile(r'[.\s\(\)\[\]][Ss]([0-9]{1,2})[Ee][0-9]{1,2}[.\s\(\)\[\]]')
YEAR_PATTERN = re.compile(r'[.\s\(\)\[\]](19[0-9]{2}|20[0-9]{2})[.\s\(\)\[\]]')

# 用于识别电视剧的模式（包含SxxExx格式）
TV_SHOW_PATTERN = re.compile(r'[.\s\(\)\[\]][Ss][0-9]{1,2}[Ee][0-9]{1,2}[.\s\(\)\[\]]')

# 用于提取分辨率和编码的模式
RESOLUTION_PATTERN = re.compile(r'[.\s\(\)\[\]](\d+p)[.\s\(\)\[\]]')
CODEC_PATTERN = re.compile(r'[.\s\(\)\[\]](x26[45])[.\s\(\)\[\]-]')

# 用于替换文件名中的分隔符的模式
SEPARATOR_PATTERN = re.compile(r'[\s\(\)\[\]]')


def is_tv_show(filename):
    """
    判断文件是否为电视剧（通过查找SxxExx格式）
    
    Args:
        filename: 文件名
        
    Returns:
        bool: 是否为电视剧
    """
    return bool(TV_SHOW_PATTERN.search(filename))


def match_resolution_and_codec(filename, target_resolution=None, target_codec=None):
    """
    检查文件是否匹配目标分辨率和编码
    
    Args:
        filename: 文件名
        target_resolution: 目标分辨率 (例如: "1080p")
        target_codec: 目标编码 (例如: "x265")
        
    Returns:
        bool: 是否匹配目标分辨率和编码
    """
    # 如果没有指定分辨率和编码，则匹配所有文件
    if not target_resolution and not target_codec:
        return True
    
    # 检查分辨率
    if target_resolution:
        resolution_match = RESOLUTION_PATTERN.search(filename)
        if not resolution_match or resolution_match.group(1).lower() != target_resolution.lower():
            return False
    
    # 检查编码
    if target_codec:
        codec_match = CODEC_PATTERN.search(filename)
        if not codec_match or codec_match.group(1).lower() != target_codec.lower():
            return False
    
    return True


def normalize_filename(filename):
    """
    将文件名中的空格、()、[]等分隔符统一替换为点号(.)
    
    Args:
        filename: 原始文件名
        
    Returns:
        str: 标准化后的文件名
    """
    # 替换所有空格、()、[]为点号
    normalized = SEPARATOR_PATTERN.sub('.', filename)
    # 处理可能出现的连续点号
    while '..' in normalized:
        normalized = normalized.replace('..', '.')
    return normalized


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
    
    # 标准化文件名（替换空格、()、[]为点号）
    normalized_basename = normalize_filename(basename)
    
    # 提取季数
    season_match = SEASON_PATTERN.search(normalized_basename)
    if not season_match:
        logging.warning(f"无法从 {filename} 中提取季数")
        return None, None
    
    season_num = int(season_match.group(1))
    season_str = f"S{season_num:02d}"
    
    # 提取剧名（假设剧名在年份之前或季数之前）
    year_match = YEAR_PATTERN.search(normalized_basename)
    
    if year_match:
        # 如果有年份，剧名在年份之前
        show_name_parts = normalized_basename[:year_match.start()].split('.')
    else:
        # 否则，剧名在季数之前
        show_name_parts = normalized_basename[:season_match.start()].split('.')
    
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
    # 标准化剧名（将空格替换为点号）
    normalized_show_name = normalize_filename(show_name)
    
    # 创建剧名目录
    show_dir = os.path.join(base_dir, normalized_show_name)
    if not os.path.exists(show_dir):
        os.makedirs(show_dir)
        logging.info(f"创建剧名目录: {show_dir}")
    
    # 创建季目录
    season_dir = os.path.join(show_dir, season)
    if not os.path.exists(season_dir):
        os.makedirs(season_dir)
        logging.info(f"创建季目录: {season_dir}")
    
    return season_dir


def can_remove_directory(directory):
    """
    检查目录是否可以删除（为空或只包含被忽略的文件类型）
    
    Args:
        directory: 目录路径
        
    Returns:
        bool: 是否可以删除目录
    """
    # 检查目录是否存在
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return False
    
    # 获取目录中的所有文件
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    
    # 如果目录为空，可以删除
    if not files:
        return True
    
    # 检查是否只包含被忽略的文件类型
    for file in files:
        _, ext = os.path.splitext(file)
        if ext.lower() not in IGNORED_EXTENSIONS:
            return False
    
    return True


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
    
    # 获取文件扩展名
    _, ext = os.path.splitext(filename)
    
    # 标准化文件名（替换空格、()、[]为点号）
    normalized_filename = normalize_filename(filename)
    
    # 保留原始扩展名
    if normalized_filename.endswith(ext):
        normalized_filename = normalized_filename[:-len(ext)] + ext
    
    target_path = os.path.join(target_dir, normalized_filename)
    
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


def process_directory(source_dir, target_base_dir, resolution=None, codec=None, remove_source=False):
    """
    处理源目录中的所有文件
    
    Args:
        source_dir: 源目录
        target_base_dir: 目标基础目录
        resolution: 目标分辨率 (例如: "1080p")
        codec: 目标编码 (例如: "x265")
        remove_source: 是否在处理后删除源目录
        
    Returns:
        tuple: (成功数, 失败数, 跳过数, 删除目录数)
    """
    success_count = 0
    failure_count = 0
    skipped_count = 0
    removed_dirs_count = 0
    
    # 收集处理过的目录，用于后续检查是否可以删除
    processed_dirs = set()
    
    # 遍历源目录中的所有文件
    for root, _, files in os.walk(source_dir, topdown=False):
        for filename in files:
            # 检查文件扩展名是否受支持
            _, ext = os.path.splitext(filename)
            if ext.lower() not in SUPPORTED_EXTENSIONS:
                continue
            
            # 检查是否为电视剧
            if not is_tv_show(filename):
                logging.info(f"跳过电影文件: {filename}")
                skipped_count += 1
                continue
            
            # 检查是否匹配目标分辨率和编码
            if not match_resolution_and_codec(filename, resolution, codec):
                logging.info(f"跳过不匹配的文件: {filename}")
                skipped_count += 1
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
            logging.info(f"目标目录: {target_dir} (剧名: {show_name}, 季: {season})")
            
            # 移动文件
            if move_file(source_path, target_dir):
                success_count += 1
                # 记录处理过的目录
                processed_dirs.add(os.path.dirname(source_path))
            else:
                failure_count += 1
    
    # 如果需要删除源目录
    if remove_source:
        # 按照目录深度从深到浅排序，确保先删除子目录
        sorted_dirs = sorted(processed_dirs, key=lambda x: x.count(os.sep), reverse=True)
        
        for dir_path in sorted_dirs:
            if can_remove_directory(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    logging.info(f"删除源目录: {dir_path}")
                    removed_dirs_count += 1
                except Exception as e:
                    logging.error(f"删除源目录失败: {dir_path}, 错误: {e}")
    
    return success_count, failure_count, skipped_count, removed_dirs_count


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='将电视剧文件移动到按剧名/季级组织的目录结构中')
    parser.add_argument('source_dir', help='源目录')
    parser.add_argument('target_dir', help='目标目录')
    parser.add_argument('--resolution', help='只处理指定分辨率的文件 (例如: 1080p, 720p)')
    parser.add_argument('--codec', help='只处理指定编码的文件 (例如: x265, x264)')
    parser.add_argument('--remove-source', action='store_true', help='移动文件后删除源目录（如果源目录为空或只剩下nfo、txt、jpg等文件）')
    parser.add_argument('--version', action='version', version=f'mv2tvdir {__version__}')
    
    args = parser.parse_args()
    
    source_dir = args.source_dir
    target_dir = args.target_dir
    resolution = args.resolution
    codec = args.codec
    remove_source = args.remove_source
    
    # 检查源目录和目标目录是否存在
    if not os.path.isdir(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        sys.exit(1)
    
    if not os.path.isdir(target_dir):
        print(f"错误: 目标目录不存在: {target_dir}")
        sys.exit(1)
    
    # 记录过滤条件
    filter_info = ""
    if resolution:
        filter_info += f", 分辨率 = {resolution}"
    if codec:
        filter_info += f", 编码 = {codec}"
    if remove_source:
        filter_info += f", 删除源目录 = 是"
    
    logging.info(f"mv2tvdir v{__version__} - 开始处理: 源目录 = {source_dir}, 目标目录 = {target_dir}{filter_info}")
    
    # 处理目录
    success_count, failure_count, skipped_count, removed_dirs_count = process_directory(
        source_dir, target_dir, resolution, codec, remove_source
    )
    
    # 输出处理结果
    result_info = f"处理完成: 成功 = {success_count}, 失败 = {failure_count}, 跳过 = {skipped_count}"
    if remove_source:
        result_info += f", 删除源目录 = {removed_dirs_count}"
    
    logging.info(result_info)


if __name__ == "__main__":
    main()