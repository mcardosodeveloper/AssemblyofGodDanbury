from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
import asyncpg
import uuid
import os
from datetime import datetime, date, timedelta
from contextlib import asynccontextmanager

# Configuração do banco
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://neondb_owner:npg_EuloKk2PDvj3@ep-steep-morning-acb05ltn-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require")

# Configuração JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "sua-chave-secreta-muito-segura-aqui-123456789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Configuração de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Usuários simples (em produção, use banco de dados)
USERS = {
    "admin": {
        "username": "admin",
        "password": pwd_context.hash("admin123"),  # Senha: admin123
        "role": "admin"
    }
}

# Função para obter conexão
async def get_connection():
    return await asyncpg.connect(DATABASE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Criar tabela
    conn = await get_connection()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cadastros (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                nome VARCHAR(255) NOT NULL,
                telefone VARCHAR(20) NOT NULL,
                email VARCHAR(255),
                data_nascimento DATE,
                endereco TEXT,
                possui_igreja VARCHAR(10),
                qual_igreja VARCHAR(255),
                como_conheceu VARCHAR(100),
                interesse VARCHAR(100),
                observacoes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    finally:
        await conn.close()
    
    yield

# FastAPI app
app = FastAPI(
    title="Sistema de Cadastro Igreja",
    description="CRUD simples para cadastro de membros",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de Autenticação
class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Funções de Autenticação
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(username: str, password: str):
    user = USERS.get(username)
    if not user or not verify_password(password, user["password"]):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = USERS.get(username)
    if user is None:
        raise credentials_exception
    return user

# Modelos Pydantic
class CadastroCreate(BaseModel):
    nome: str
    telefone: str
    email: Optional[str] = None
    data_nascimento: Optional[date] = None
    endereco: Optional[str] = None
    possui_igreja: Optional[str] = None
    qual_igreja: Optional[str] = None
    como_conheceu: Optional[str] = None
    interesse: Optional[str] = None
    observacoes: Optional[str] = None

class CadastroUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    data_nascimento: Optional[date] = None
    endereco: Optional[str] = None
    possui_igreja: Optional[str] = None
    qual_igreja: Optional[str] = None
    como_conheceu: Optional[str] = None
    interesse: Optional[str] = None
    observacoes: Optional[str] = None

class CadastroResponse(BaseModel):
    id: uuid.UUID
    nome: str
    telefone: str
    email: Optional[str]
    data_nascimento: Optional[date]
    endereco: Optional[str]
    possui_igreja: Optional[str]
    qual_igreja: Optional[str]
    como_conheceu: Optional[str]
    interesse: Optional[str]
    observacoes: Optional[str]
    created_at: datetime
    updated_at: datetime

# Endpoints

@app.get("/")
async def root():
    """Servir página de login"""
    return FileResponse("index.html", media_type="text/html")

@app.get("/api")
async def api_info():
    return {
        "message": "Sistema de Cadastro Igreja - CRUD Simples",
        "status": "online",
        "endpoints": {
            "login": "POST /api/login",
            "criar": "POST /api/cadastro (protegido)",
            "listar": "GET /api/cadastros (protegido)",
            "obter": "GET /api/cadastro/{id} (protegido)",
            "atualizar": "PUT /api/cadastro/{id} (protegido)",
            "deletar": "DELETE /api/cadastro/{id} (protegido)",
            "estatisticas": "GET /api/stats (protegido)"
        },
        "interface": "GET /cadastros - Interface web para visualizar cadastros (protegida)"
    }

@app.post("/api/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Fazer login e obter token JWT"""
    user = authenticate_user(user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/cadastros")
async def pagina_cadastros(current_user: dict = Depends(get_current_user)):
    """Servir página de listagem de cadastros (protegida)"""
    return FileResponse("cadastros.html", media_type="text/html")

@app.post("/api/cadastro", response_model=dict)
async def criar_cadastro(cadastro: CadastroCreate, current_user: dict = Depends(get_current_user)):
    """Criar novo cadastro"""
    conn = await get_connection()
    try:
            # Verificar se telefone já existe
            existing = await conn.fetchrow(
                "SELECT id FROM cadastros WHERE telefone = $1",
                cadastro.telefone
            )
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Já existe cadastro com o telefone {cadastro.telefone}"
                )
            
            # Inserir novo cadastro
            result = await conn.fetchrow("""
                INSERT INTO cadastros (
                    nome, telefone, email, data_nascimento, endereco,
                    possui_igreja, qual_igreja, como_conheceu, interesse, observacoes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id, created_at
            """, 
                cadastro.nome, cadastro.telefone, cadastro.email,
                cadastro.data_nascimento, cadastro.endereco, cadastro.possui_igreja,
                cadastro.qual_igreja, cadastro.como_conheceu, cadastro.interesse,
                cadastro.observacoes
            )
            
            return {
                "success": True,
                "message": "Cadastro criado com sucesso!",
                "id": str(result["id"]),
                "created_at": result["created_at"]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    finally:
        await conn.close()

@app.get("/api/cadastros", response_model=List[CadastroResponse])
async def listar_cadastros(
    limit: int = 50,
    offset: int = 0,
    nome: Optional[str] = None,
    interesse: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Listar cadastros com filtros opcionais"""
    conn = await get_connection()
    try:
            # Construir query com filtros
            where_conditions = []
            params = []
            param_count = 0
            
            if nome:
                param_count += 1
                where_conditions.append(f"nome ILIKE ${param_count}")
                params.append(f"%{nome}%")
            
            if interesse:
                param_count += 1
                where_conditions.append(f"interesse = ${param_count}")
                params.append(interesse)
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            param_count += 1
            params.append(limit)
            param_count += 1
            params.append(offset)
            
            query = f"""
                SELECT * FROM cadastros
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count-1} OFFSET ${param_count}
            """
            
            rows = await conn.fetch(query, *params)
            
            cadastros = []
            for row in rows:
                cadastros.append(CadastroResponse(**dict(row)))
            
            return cadastros
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    finally:
        await conn.close()

@app.get("/api/cadastro/{cadastro_id}", response_model=CadastroResponse)
async def obter_cadastro(cadastro_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    """Obter cadastro por ID"""
    conn = await get_connection()
    try:
            row = await conn.fetchrow(
                "SELECT * FROM cadastros WHERE id = $1",
                cadastro_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Cadastro não encontrado")
            
            return CadastroResponse(**dict(row))
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    finally:
        await conn.close()

@app.put("/api/cadastro/{cadastro_id}", response_model=dict)
async def atualizar_cadastro(cadastro_id: uuid.UUID, cadastro: CadastroUpdate, current_user: dict = Depends(get_current_user)):
    """Atualizar cadastro existente"""
    conn = await get_connection()
    try:
            # Verificar se cadastro existe
            existing = await conn.fetchrow(
                "SELECT id FROM cadastros WHERE id = $1",
                cadastro_id
            )
            
            if not existing:
                raise HTTPException(status_code=404, detail="Cadastro não encontrado")
            
            # Construir query de update dinâmica
            updates = []
            params = []
            param_count = 0
            
            for field, value in cadastro.dict(exclude_unset=True).items():
                param_count += 1
                updates.append(f"{field} = ${param_count}")
                params.append(value)
            
            if not updates:
                raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
            
            # Verificar telefone duplicado se foi alterado
            if "telefone" in cadastro.dict(exclude_unset=True):
                existing_phone = await conn.fetchrow(
                    "SELECT id FROM cadastros WHERE telefone = $1 AND id != $2",
                    cadastro.telefone, cadastro_id
                )
                if existing_phone:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Já existe outro cadastro com o telefone {cadastro.telefone}"
                    )
            
            param_count += 1
            params.append(datetime.now())
            param_count += 1
            params.append(cadastro_id)
            
            query = f"""
                UPDATE cadastros 
                SET {', '.join(updates)}, updated_at = ${param_count-1}
                WHERE id = ${param_count}
                RETURNING updated_at
            """
            
            result = await conn.fetchrow(query, *params)
            
            return {
                "success": True,
                "message": "Cadastro atualizado com sucesso!",
                "updated_at": result["updated_at"]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    finally:
        await conn.close()

@app.delete("/api/cadastro/{cadastro_id}", response_model=dict)
async def deletar_cadastro(cadastro_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    """Deletar cadastro"""
    conn = await get_connection()
    try:
            result = await conn.fetchrow(
                "DELETE FROM cadastros WHERE id = $1 RETURNING id",
                cadastro_id
            )
            
            if not result:
                raise HTTPException(status_code=404, detail="Cadastro não encontrado")
            
            return {
                "success": True,
                "message": "Cadastro deletado com sucesso!"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    finally:
        await conn.close()

@app.get("/api/stats")
async def obter_estatisticas(current_user: dict = Depends(get_current_user)):
    """Estatísticas dos cadastros"""
    conn = await get_connection()
    try:
            # Total de cadastros
            total_result = await conn.fetchrow("SELECT COUNT(*) as total FROM cadastros")
            total_cadastros = total_result["total"]
            
            # Cadastros hoje
            hoje_result = await conn.fetchrow("""
                SELECT COUNT(*) as total FROM cadastros 
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            cadastros_hoje = hoje_result["total"]
            
            # Por interesse
            interesse_rows = await conn.fetch("""
                SELECT interesse, COUNT(*) as count 
                FROM cadastros 
                WHERE interesse IS NOT NULL 
                GROUP BY interesse 
                ORDER BY count DESC
            """)
            por_interesse = [dict(row) for row in interesse_rows]
            
            # Por como conheceu
            conheceu_rows = await conn.fetch("""
                SELECT como_conheceu, COUNT(*) as count 
                FROM cadastros 
                WHERE como_conheceu IS NOT NULL 
                GROUP BY como_conheceu 
                ORDER BY count DESC
            """)
            por_como_conheceu = [dict(row) for row in conheceu_rows]
            
            # Com email
            email_result = await conn.fetchrow("""
                SELECT COUNT(*) as count FROM cadastros 
                WHERE email IS NOT NULL AND email != ''
            """)
            com_email = email_result["count"]
            
            return {
                "total_cadastros": total_cadastros,
                "cadastros_hoje": cadastros_hoje,
                "com_email": com_email,
                "sem_email": total_cadastros - com_email,
                "por_interesse": por_interesse,
                "por_como_conheceu": por_como_conheceu
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    finally:
        await conn.close()

@app.get("/health")
async def health_check():
    """Health check"""
    try:
        conn = await get_connection()
        try:
            await conn.fetchrow("SELECT 1")
        finally:
            await conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now()
        }

# Servir arquivos estáticos (opcional)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass  # Caso a pasta static não exista

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)