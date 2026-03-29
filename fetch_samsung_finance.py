import os
import pandas as pd
import OpenDartReader
from dotenv import load_dotenv

def main():
    # 1. 별도 파일(.env)에서 DART API 키 로드
    load_dotenv()
    api_key = os.getenv('DART_API_KEY')

    if not api_key or api_key == '이곳에_API_키를_입력하세요':
        print("오류: DART_API_KEY가 설정되지 않았습니다.")
        print(".env 파일에 DART API 키를 입력해주세요.")
        return

    print("DART API를 통해 삼성전자의 지난 10년치 재무정보를 가져오는 중입니다...")
    
    # OpenDartReader 초기화
    dart = OpenDartReader(api_key)
    company = '삼성전자'
    
    # 최근 10년 (2015 ~ 2024년, 아직 2024년 사업보고서가 없을 수 있으므로 예외처리 포함)
    years = range(2015, 2025)
    frames = []

    for year in years:
        try:
            # 사업보고서(11011) 주요 재무제표 데이터 가져오기
            df = dart.finstate(company, year, reprt_code='11011')
            
            if df is not None and not df.empty:
                # 연결재무제표(CFS)만 필터링
                if 'fs_div' in df.columns:
                    df_cfs = df[df['fs_div'] == 'CFS']
                else:
                    df_cfs = df
                
                # 주요 계정 필터링 (명칭이 약간씩 다를 수 있으므로 포함 여부로 체크할 수도 있지만, 표준 계정명 사용)
                target_accounts = ['자산총계', '부채총계', '자본총계', '매출액', '영업이익', '당기순이익']
                filtered_df = df_cfs[df_cfs['account_nm'].isin(target_accounts)].copy()
                
                # 중복 계정 제거 (가끔 동일 계정이 여러번 나올 수 있음)
                filtered_df = filtered_df.drop_duplicates(subset=['account_nm'], keep='first')
                
                # 필요한 열만 추출
                filtered_df = filtered_df[['account_nm', 'thstrm_amount']]
                filtered_df.rename(columns={'thstrm_amount': str(year)}, inplace=True)
                filtered_df.set_index('account_nm', inplace=True)
                
                # 문자열 금액을 숫자로 변환 (쉼표 제거)
                filtered_df[str(year)] = pd.to_numeric(filtered_df[str(year)].astype(str).str.replace(',', ''), errors='coerce')
                
                frames.append(filtered_df)
                print(f" - {year}년 데이터 수집 완료")
            else:
                print(f" - {year}년 데이터가 없습니다.")
        except Exception as e:
            print(f" - {year}년 데이터 수집 실패 (오류: {e})")

    if frames:
        # 연도별 데이터 병합
        result_df = pd.concat(frames, axis=1)
        
        # 행 순서 정렬
        order = ['매출액', '영업이익', '당기순이익', '자산총계', '부채총계', '자본총계']
        existing_order = [acc for acc in order if acc in result_df.index]
        result_df = result_df.reindex(existing_order)
        
        # 엑셀 파일로 저장
        excel_file = '삼성전자_주요재무정보_10년.xlsx'
        result_df.to_excel(excel_file)
        print(f"\n[성공] 데이터가 성공적으로 엑셀 파일로 저장되었습니다: {excel_file}")
        
        # 표 형식으로 출력 (숫자 포맷팅: 천 단위 콤마 추가)
        print("\n[삼성전자 주요 재무정보 10년 (단위: 원)]")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        
        result_df_display = result_df.map(lambda x: f"{x:,.0f}" if pd.notnull(x) else "-")
        print(result_df_display.to_markdown())
    else:
        print("수집된 데이터가 없습니다.")

if __name__ == '__main__':
    main()
