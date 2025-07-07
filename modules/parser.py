import bs4
from markdownify import markdownify as md
import urllib.parse



def convert_html_to_markdown_v3(html_string: str, base_domain: str = "https://nguoidonghanh.viettel.vn") -> str:
    """
    Chuyển đổi HTML sang Markdown, xử lý URL hình ảnh, link tương đối,
    và bỏ qua các URL (src, href) có độ dài quá lớn.

    Args:
        html_string: Chuỗi HTML đầu vào.
        base_domain: Tên miền để thêm vào trước các đường dẫn tương đối.

    Returns:
        Chuỗi đã được định dạng Markdown.
    """
    # Hằng số để dễ dàng thay đổi giới hạn độ dài
    MAX_URL_LENGTH = 300
    
    soup = bs4.BeautifulSoup(html_string, 'lxml')
    
    # --- BƯỚC 1: TIỀN XỬ LÝ - Loại bỏ các link và ảnh có URL quá dài ---

    # 1.1: Xử lý các thẻ <a> (hyperlinks) có href quá dài
    for a_tag in soup.find_all('a'):
        href = a_tag.get('href')
        if href and len(href) > MAX_URL_LENGTH:
            # "unwrap" thẻ <a>: loại bỏ tag nhưng giữ lại nội dung text bên trong
            a_tag.unwrap()

    # 1.2: Xử lý các thẻ <img> có src quá dài hoặc là đường dẫn tương đối
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            # Kiểm tra nếu src quá dài
            if len(src) > MAX_URL_LENGTH:
                # Loại bỏ hoàn toàn thẻ img nếu src quá dài
                img.decompose()
                continue # Chuyển sang thẻ img tiếp theo
            
            # Nếu src là đường dẫn tương đối, tạo URL đầy đủ
            if src.startswith('/'):
                full_url = urllib.parse.urljoin(base_domain, src)
                # Kiểm tra lại độ dài sau khi đã nối domain
                if len(full_url) > MAX_URL_LENGTH:
                    img.decompose()
                else:
                    img['src'] = full_url
        else:
            # Nếu thẻ img không có src, cũng loại bỏ luôn
            img.decompose()


    # --- BƯỚC 2: CHUYỂN ĐỔI SANG MARKDOWN (Logic gần như giữ nguyên) ---
    markdown_parts = []
    
    def encode_url(url: str) -> str:
        if not url:
            return ""
        scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(url)
        path = urllib.parse.quote(path)
        return urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment))

    # Bây giờ, các thẻ đã được làm sạch, chúng ta chỉ cần xử lý như bình thường
    for element in soup.find_all(['p', 'table', 'div']):
        if element.name == 'table' and 'table-image' in element.get('class', []):
            img_tag = element.find('img')
            caption_td = element.find('td', class_='image-caption')

            if img_tag:
                alt_text = img_tag.get('caption', img_tag.get('alt', '')).strip()
                src = encode_url(img_tag.get('src', ''))
                markdown_parts.append(f"![{alt_text}]({src})")

                if caption_td:
                    caption_text = caption_td.get_text(strip=True)
                    markdown_parts.append(f"{caption_text}")

        elif element.name in ['p', 'div']:
            img_in_element = element.find('img')

            if img_in_element:
                alt_text = img_in_element.get('caption', img_in_element.get('alt', '')).strip()
                src = encode_url(img_in_element.get('src', ''))
                
                if src:
                    markdown_parts.append(f"![{alt_text}]({src})")

                element_text = element.get_text(strip=True)
                if element_text and (not markdown_parts or markdown_parts[-1] != f"{element_text}"):
                    if element_text != '\xa0': 
                         markdown_parts.append(f"{element_text}")
            else:
                if element.get_text(strip=True) or element.find_all():
                    if element.get_text(strip=True) == '\xa0':
                        continue
                    p_markdown = md(str(element)).strip()
                    if p_markdown:
                        markdown_parts.append(p_markdown)

    final_output = []
    for part in markdown_parts:
        if part not in final_output:
            final_output.append(part)
            
    return "\n\n".join(final_output)