/**
 * Curated example branches/majors for each family of existing qualifications.
 * Degree titles come from the user's separate, 210-title reference index;
 * branches do NOT come from that PDF and are not a global verified register.
 * Students can always type their official unlisted branch name.
 */
import { canonicalCurrentDegree } from './currentDegreeTitles'

const ENGINEERING = [
  'Computer Science and Engineering', 'Information Technology',
  'Artificial Intelligence and Machine Learning', 'Data Science',
  'Electronics and Communication Engineering', 'Electrical Engineering',
  'Mechanical Engineering', 'Civil Engineering', 'Chemical Engineering',
  'Aerospace Engineering', 'Automobile Engineering', 'Biomedical Engineering',
  'Biotechnology', 'Environmental Engineering', 'Industrial Engineering',
  'Instrumentation and Control Engineering', 'Mechatronics Engineering',
  'Robotics and Automation', 'Materials Science and Engineering',
  'Mining Engineering', 'Petroleum Engineering', 'Structural Engineering',
  'Telecommunications Engineering', 'Renewable Energy Engineering',
]
const COMPUTING = [
  'Computer Science', 'Software Engineering', 'Information Technology',
  'Artificial Intelligence', 'Machine Learning', 'Data Science',
  'Cybersecurity', 'Cloud Computing', 'Computer Networks',
  'Web Development', 'Mobile Application Development', 'Information Systems',
  'Database Systems', 'Human-Computer Interaction', 'Computer Graphics',
]
const SCIENCES = [
  'Physics', 'Chemistry', 'Mathematics', 'Statistics', 'Computer Science',
  'Biology', 'Biotechnology', 'Biochemistry', 'Microbiology', 'Botany',
  'Zoology', 'Environmental Science', 'Earth Science', 'Geology',
  'Astronomy', 'Genetics', 'Forensic Science', 'Psychology', 'Food Science',
  'Neuroscience', 'Data Science',
]
const ARTS = [
  'English Literature', 'History', 'Political Science', 'Economics',
  'Psychology', 'Sociology', 'Philosophy', 'Geography', 'Anthropology',
  'Linguistics', 'Languages', 'Journalism', 'International Relations',
  'Fine Arts', 'Performing Arts', 'Public Administration', 'Social Work',
  'Religious Studies', 'Media Studies',
]
const BUSINESS = [
  'Accounting', 'Finance', 'Marketing', 'Human Resource Management',
  'Business Analytics', 'Operations Management', 'International Business',
  'Entrepreneurship', 'Supply Chain Management', 'Strategic Management',
  'Economics', 'Digital Marketing', 'Banking and Insurance',
  'Project Management', 'Business Information Systems',
]
const COMMERCE = [
  'Accounting', 'Finance', 'Banking', 'Taxation', 'Auditing', 'Economics',
  'Business Management', 'Financial Markets', 'Business Analytics',
  'International Trade', 'Insurance', 'Corporate Accounting',
]
const EDUCATION = [
  'Early Childhood Education', 'Primary Education', 'Secondary Education',
  'Special Education', 'Educational Leadership', 'Curriculum and Instruction',
  'Educational Technology', 'Mathematics Education', 'Science Education',
  'Language Education', 'Physical Education', 'Counselling and Guidance',
]
const HEALTH = [
  'Public Health', 'Community Health', 'Health Administration',
  'Clinical Sciences', 'Epidemiology', 'Biostatistics', 'Health Policy',
  'Health Informatics', 'Nutrition and Dietetics', 'Healthcare Management',
]
const MEDICINE = [
  'General Medicine', 'Internal Medicine', 'Pediatrics', 'General Surgery',
  'Obstetrics and Gynecology', 'Anesthesiology', 'Psychiatry', 'Radiology',
  'Dermatology', 'Emergency Medicine', 'Family Medicine', 'Pathology',
]
const NURSING = [
  'General Nursing', 'Adult Health Nursing', 'Pediatric Nursing',
  'Community Health Nursing', 'Psychiatric Nursing', 'Critical Care Nursing',
  'Midwifery', 'Nursing Administration', 'Nursing Education',
]
const DESIGN = [
  'Graphic Design', 'Interaction Design', 'Product Design',
  'Industrial Design', 'Communication Design', 'Fashion Design',
  'User Experience Design', 'Interior Design', 'Animation',
  'Visual Communication', 'Textile Design',
]
const ARCHITECTURE = [
  'Architectural Design', 'Urban Design', 'Landscape Architecture',
  'Sustainable Architecture', 'Building Technology',
  'Architectural Conservation', 'Urban Planning', 'Interior Architecture',
]
const AGRICULTURE = [
  'Agronomy', 'Soil Science', 'Horticulture', 'Plant Breeding and Genetics',
  'Agricultural Economics', 'Animal Science', 'Agricultural Engineering',
  'Plant Pathology', 'Entomology', 'Agricultural Biotechnology',
]
const MEDIA = [
  'Journalism', 'Mass Communication', 'Digital Media', 'Film and Television',
  'Advertising', 'Public Relations', 'Media Studies', 'Photojournalism',
  'Broadcasting', 'Visual Communication',
]
const LAW = [
  'Constitutional Law', 'Criminal Law', 'Corporate Law', 'International Law',
  'Intellectual Property Law', 'Environmental Law', 'Human Rights Law',
  'Tax Law', 'Civil Law', 'Commercial Law',
]
const HUMANITIES = [...ARTS, 'Cultural Studies', 'Gender Studies']
const SOCIAL = [
  'Sociology', 'Psychology', 'Social Work', 'Political Science',
  'Economics', 'Public Policy', 'Human Geography', 'International Relations',
  'Anthropology', 'Criminology', 'Development Studies',
]
const ENVIRONMENT = [
  'Ecology', 'Environmental Science', 'Environmental Management',
  'Climate Science', 'Conservation Biology', 'Environmental Policy',
  'Sustainability', 'Natural Resource Management', 'Geography',
]
const HOTEL = [
  'Hotel Operations', 'Hospitality Management', 'Food and Beverage Management',
  'Culinary Arts', 'Tourism Management', 'Event Management',
  'Travel and Tourism', 'Hospitality Marketing',
]
const SPORT = [
  'Physical Education', 'Sports Science', 'Exercise Physiology',
  'Sports Management', 'Health and Fitness', 'Coaching', 'Sports Psychology',
]
const MUSIC = [
  'Vocal Performance', 'Instrumental Performance', 'Music Theory',
  'Music Composition', 'Music Education', 'Music Production',
  'Ethnomusicology', 'Music Technology',
]
const VISUAL_ARTS = [
  'Painting', 'Sculpture', 'Photography', 'Illustration', 'Digital Arts',
  'Animation', 'Ceramics', 'Printmaking', 'Art History',
]
const PHARMACY = [
  'Pharmaceutics', 'Pharmacology', 'Pharmaceutical Chemistry',
  'Pharmacognosy', 'Clinical Pharmacy', 'Pharmacy Practice',
  'Pharmaceutical Biotechnology', 'Regulatory Affairs',
]
const SPECIALIZED: readonly [RegExp, readonly string[]][] = [
  [/computer science|computer applications|software engineering|information technology|information systems|^information$/i, COMPUTING],
  [/engineering management/i, [...ENGINEERING, ...BUSINESS]],
  [/engineering|^technology$|surveying/i, ENGINEERING],
  [/applied science|^science$|science by research/i, [...SCIENCES, ...ENGINEERING]],
  [/statistics|mathematics|actuarial science/i, ['Mathematics', 'Applied Mathematics', 'Statistics', 'Data Science', 'Actuarial Science', 'Financial Mathematics', 'Biostatistics', 'Operations Research']],
  [/accounting|accountancy/i, ['Accounting', 'Auditing', 'Taxation', 'Forensic Accounting', 'Financial Accounting', 'Management Accounting', 'Corporate Finance']],
  [/banking|finance|financial management/i, ['Finance', 'Financial Markets', 'Banking', 'Investment Management', 'Risk Management', 'Financial Planning', 'Insurance', 'Financial Technology']],
  [/economics/i, ['Economics', 'Applied Economics', 'Econometrics', 'Development Economics', 'International Economics', 'Financial Economics']],
  [/hospitality|hotel|tourism|travel/i, HOTEL],
  [/health administration|hospital administration/i, HEALTH],
  [/landscape architecture/i, ['Landscape Architecture', 'Landscape Design', 'Landscape Planning', 'Ecological Design', 'Urban Landscape']],
  [/interior design/i, ['Interior Design', 'Interior Architecture', 'Space Planning', 'Furniture Design', 'Sustainable Interiors']],
  [/architecture|architectural|built environment|urban design|urban planning|city planning|^planning$|building science|construction management/i, ARCHITECTURE],
  [/design|creative arts/i, DESIGN],
  [/forestry/i, ['Forestry', 'Forest Management', 'Forest Ecology', 'Wood Science', 'Conservation Forestry', 'Agroforestry']],
  [/fisheries/i, ['Fisheries Science', 'Aquaculture', 'Marine Biology', 'Fish Processing', 'Aquatic Ecology']],
  [/horticulture/i, ['Horticulture', 'Floriculture', 'Fruit Science', 'Vegetable Science', 'Landscape Horticulture']],
  [/agricultur|agribusiness|animal science|food technology/i, [...AGRICULTURE, 'Food Technology', 'Food Safety', 'Food Processing']],
  [/veterinary/i, ['Veterinary Medicine', 'Veterinary Surgery', 'Animal Nutrition', 'Veterinary Pathology', 'Veterinary Public Health']],
  [/environment|natural resource/i, ENVIRONMENT],
  [/public policy|public affairs|public administration|public management/i, ['Public Administration', 'Public Policy', 'Governance', 'International Relations', 'Political Science', 'Development Studies']],
  [/business|commerce|management|entrepreneurship/i, [...BUSINESS, ...COMMERCE]],
  [/journalism|communication|media/i, MEDIA],
  [/music education/i, [...MUSIC, ...EDUCATION]],
  [/music/i, MUSIC],
  [/visual arts|fine arts/i, VISUAL_ARTS],
  [/dance|performing arts|dramatic art/i, ['Dance', 'Drama', 'Theatre Studies', 'Acting', 'Choreography', 'Stage Production', 'Performing Arts']],
  [/physical education/i, SPORT],
  [/education|teaching|educational leadership/i, EDUCATION],
  [/law|legal/i, LAW],
  [/social work|social science|social service|criminology|psychology|international studies/i, SOCIAL],
  [/library|information science/i, ['Library Science', 'Information Management', 'Digital Libraries', 'Knowledge Management', 'Information Science', 'Archives']],
  [/theolog|divinity|ministry|religious/i, ['Theology', 'Biblical Studies', 'Religious Studies', 'Pastoral Studies', 'Church History', 'Ethics']],
  [/public health/i, HEALTH],
  [/nursing|midwifery/i, NURSING],
  [/pharmacy/i, PHARMACY],
  [/dental surgery/i, ['Dentistry', 'Orthodontics', 'Prosthodontics', 'Periodontology', 'Oral Surgery', 'Endodontics', 'Public Health Dentistry']],
  [/physiotherapy|occupational therapy|optometry/i, ['General Practice', 'Pediatric Care', 'Geriatric Care', 'Rehabilitation', 'Neurological Rehabilitation', 'Sports Rehabilitation']],
  [/health science|biomedical science|allied health/i, HEALTH],
  [/medicine|medical science|clinical science|surgery|paramedicine/i, MEDICINE],
  [/arts and sciences|interdisciplinary|general studies|professional studies|advanced stud|^studies$|philosophy|research/i, [...SCIENCES, ...ARTS, ...BUSINESS]],
  [/liberal arts|liberal studies|humanities|letters|^arts$|applied arts/i, HUMANITIES],
]
const GENERAL = [...SCIENCES, ...ARTS, ...COMPUTING, ...BUSINESS, ...DESIGN]

/** Returns suggestions only; the actual branch is free-text to cover local naming. */
export function branchesForCurrentDegree(degreeTitle: string): string[] {
  if (!canonicalCurrentDegree(degreeTitle)) return []
  const name = degreeTitle.replace(/^(Bachelor|Master) of /, '')
  const group = SPECIALIZED.find(([pattern]) => pattern.test(name))?.[1] ?? GENERAL
  return [...new Set(['General / No specialization', ...group, 'Other / Not listed'])]
}
