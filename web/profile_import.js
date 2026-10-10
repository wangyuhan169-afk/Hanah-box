// Read a local profile file; saving uses the same profile-only path as the form.
window.HANAH_PROFILE_FROM_FILE=(input,current={})=>{
 const fields=['name','sex','birth_date','degree','major','party','degree_origin','certification','degree_title','degree_school','degree_start','degree_graduation','graduation_year','graduation_month','undergrad_school','undergrad_major','undergrad_start','undergrad_graduation','undergrad_title','undergrad_date_note','student_leadership','leadership_start','leadership_end','leadership_proof','leadership_note','work_years','higher_ed_counselor_years','work_experience','fresh','establishment','preferred_cities','preferred_categories','profile_updated_at','marital_status','preferred_region'];
 const source=input?.profile??input;
 if(!source||typeof source!=='object'||Array.isArray(source))throw Error('请选择有效的个人条件 JSON 文件');
 const values=Object.fromEntries(Object.entries(source).filter(([k,v])=>fields.includes(k)&&(typeof v==='string'||Array.isArray(v)&&v.every(x=>typeof x==='string'))));
 if(!['name','degree','major','birth_date'].some(k=>values[k]))throw Error('文件中未找到个人报考条件');
 return {...current,...values};
};
document.querySelector('#importProfile').onclick=()=>document.querySelector('#profileFile').click();
document.querySelector('#profileFile').onchange=async e=>{
 const file=e.target.files[0];if(!file)return;
 try{
  if(file.size>65536)throw Error('个人条件文件过大，请选择单独的报考条件文件');
  const input=JSON.parse((await file.text()).replace(/^\uFEFF/,''));
  await api('profile',window.HANAH_PROFILE_FROM_FILE(input,data.profile));
  document.querySelector('#profileDialog').close();await load();message('个人报考条件已更新并保存在本浏览器，岗位匹配和备考规划已重新计算。');
 }catch(error){message(error.message)}finally{e.target.value=''}
};
